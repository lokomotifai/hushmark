"""Reproducible data preparation and adoption rules for hushmark-tr."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from hushmark_core.taxonomy_gen import TAXONOMY

from hushmark_bench.dataset import MORPHOLOGIES, Example, generate_examples, load_dataset
from hushmark_bench.templates import DOMAINS, TEMPLATES

TOKEN_PATTERN = re.compile(r"\w+(?:[-_]\w+)*|\S", re.UNICODE)
BALANCE_UNIT = len(TEMPLATES) * len(MORPHOLOGIES)
DEFAULT_SYNTHETIC_EXAMPLES = math.ceil(200_000 / BALANCE_UNIT) * BALANCE_UNIT
NER_TYPES = tuple(
    entity_type for entity_type, metadata in TAXONOMY.items() if metadata["layer"] == "ner"
)
AI4PRIVACY_TYPE_ALIASES = {
    "ADDRESS": "ADDRESS",
    "BUILDINGNUMBER": "ADDRESS",
    "CITY": "ADDRESS",
    "COMPANYNAME": "ORG",
    "COUNTY": "ADDRESS",
    "DATEOFBIRTH": "DOB",
    "DOB": "DOB",
    "ETHNICITY": "ETHNICITY",
    "FIRSTNAME": "PERSON",
    "HEALTHCONDITION": "HEALTH",
    "LASTNAME": "PERSON",
    "MEDICALCONDITION": "HEALTH",
    "NAME": "PERSON",
    "ORGANIZATION": "ORG",
    "PERSON": "PERSON",
    "STREET": "ADDRESS",
}


@dataclass(frozen=True, slots=True)
class SynthesisSummary:
    examples: int
    sha256: str
    domains: dict[str, int]
    morphologies: dict[str, int]
    domain_morphologies: dict[str, int]


def scaled_examples(seed: int, count: int = DEFAULT_SYNTHETIC_EXAMPLES) -> Iterator[Example]:
    """Yield an exactly balanced scaled corpus without retaining it in memory."""

    if count < 200_000 or count % BALANCE_UNIT:
        raise ValueError(f"example count must be >=200000 and divisible by {BALANCE_UNIT}")
    yield from generate_examples(seed, repetitions=count // len(TEMPLATES))


def synthesize(
    *,
    seed: int,
    count: int = DEFAULT_SYNTHETIC_EXAMPLES,
    output_path: Path | None = None,
) -> SynthesisSummary:
    """Generate canonical JSONL, optionally writing it, and return balance evidence."""

    digest = hashlib.sha256()
    domains: Counter[str] = Counter()
    morphologies: Counter[str] = Counter()
    domain_morphologies: Counter[str] = Counter()
    output = output_path.open("w", encoding="utf-8") if output_path is not None else None
    try:
        for example in scaled_examples(seed, count):
            line = json.dumps(asdict(example), ensure_ascii=False, separators=(",", ":")) + "\n"
            digest.update(line.encode())
            if output is not None:
                output.write(line)
            morphology = example.morphology[0]
            domains[example.domain] += 1
            morphologies[morphology] += 1
            domain_morphologies[f"{example.domain}/{morphology}"] += 1
    finally:
        if output is not None:
            output.close()

    if set(domains) != set(DOMAINS) or len(set(domains.values())) != 1:
        raise RuntimeError("synthetic domains are not balanced")
    if set(morphologies) != set(MORPHOLOGIES) or len(set(morphologies.values())) != 1:
        raise RuntimeError("synthetic morphologies are not balanced")
    if (
        len(domain_morphologies) != len(DOMAINS) * len(MORPHOLOGIES)
        or len(set(domain_morphologies.values())) != 1
    ):
        raise RuntimeError("synthetic domain/morphology intersections are not balanced")
    return SynthesisSummary(
        examples=count,
        sha256=digest.hexdigest(),
        domains=dict(sorted(domains.items())),
        morphologies=dict(sorted(morphologies.items())),
        domain_morphologies=dict(sorted(domain_morphologies.items())),
    )


def load_model_labels(registry_path: Path) -> dict[str, str]:
    """Load the incumbent's closed taxonomy-to-natural-label mapping."""

    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, list):
        raise ValueError("model registry has no models list")
    for model in models:
        if isinstance(model, dict) and model.get("id") == "gliner_multi_pii-v1":
            labels = model.get("labels")
            if not isinstance(labels, dict):
                break
            normalized = {str(entity_type): str(label) for entity_type, label in labels.items()}
            if set(normalized) != set(NER_TYPES):
                raise ValueError("model registry labels do not match the closed NER taxonomy")
            return normalized
    raise ValueError("incumbent model labels are missing")


def tokenized_text(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(), match.start(), match.end()) for match in TOKEN_PATTERN.finditer(text)]


def token_span(tokens: list[tuple[str, int, int]], start: int, end: int) -> tuple[int, int]:
    starts = {token_start: index for index, (_, token_start, _) in enumerate(tokens)}
    ends = {token_end: index for index, (_, _, token_end) in enumerate(tokens)}
    if start not in starts or end not in ends:
        raise ValueError(f"entity span {start}:{end} does not align to GLiNER word boundaries")
    first, last = starts[start], ends[end]
    if first > last:
        raise ValueError(f"entity span {start}:{end} has inverted token boundaries")
    return first, last


def prepare_record(
    raw: Mapping[str, Any],
    labels: Mapping[str, str],
    *,
    source: str,
) -> dict[str, Any]:
    """Convert a character-offset example to GLiNER's inclusive token-span format."""

    text = raw.get("text")
    entities = raw.get("entities")
    if not isinstance(text, str) or not isinstance(entities, list):
        raise ValueError("training record requires text and entities")
    tokens = tokenized_text(text)
    prepared_entities: list[list[int | str]] = []
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise ValueError("training entity must be an object")
        entity_type = entity.get("type")
        if not isinstance(entity_type, str) or entity_type not in NER_TYPES:
            continue
        start, end = entity.get("start"), entity.get("end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or text[start:end] != entity.get("text")
        ):
            raise ValueError("training entity has invalid character offsets")
        first, last = token_span(tokens, start, end)
        prepared_entities.append([first, last, labels[entity_type]])
    return {
        "id": str(raw.get("id", "unknown")),
        "source": source,
        "tokenized_text": [token for token, _, _ in tokens],
        "ner": prepared_entities,
        "ner_labels": [labels[entity_type] for entity_type in NER_TYPES],
    }


def prepare_hushmark_records(data_path: Path, labels: Mapping[str, str]) -> list[dict[str, Any]]:
    return [
        prepare_record(raw, labels, source="hushmark-bench-v0") for raw in load_dataset(data_path)
    ]


def smoke_records(seed: int, labels: Mapping[str, str]) -> list[dict[str, Any]]:
    """Build 200 deterministic smoke rows that do not overlap the locked v0 benchmark."""

    # v0 uses the first eight repetitions. Start at repetition nine so smoke training
    # never sees an exact benchmark row while retaining deterministic Turkish coverage.
    generated = list(generate_examples(seed, repetitions=9))[2016:2216]
    return [
        prepare_record(asdict(example), labels, source="synthetic-post-benchmark-holdout")
        for example in generated
    ]


def normalize_ai4privacy_record(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize an exported Turkish AI4Privacy JSONL row with character spans."""

    language = raw.get("language", raw.get("lang", raw.get("locale")))
    if isinstance(language, str) and not language.lower().startswith("tr"):
        return None
    text = raw.get("text", raw.get("source_text"))
    spans = raw.get("entities", raw.get("spans"))
    if not isinstance(text, str) or not isinstance(spans, list):
        raise ValueError("AI4Privacy row requires text/source_text and entities/spans")
    entities: list[dict[str, Any]] = []
    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError("AI4Privacy span must be an object")
        external_type = span.get("type", span.get("label", span.get("entity_type")))
        if not isinstance(external_type, str):
            raise ValueError("AI4Privacy span has no type")
        compact_type = re.sub(r"[^A-Z0-9]", "", external_type.upper())
        entity_type = AI4PRIVACY_TYPE_ALIASES.get(compact_type, external_type.upper())
        if entity_type not in NER_TYPES:
            continue
        start = span.get("start", span.get("start_position"))
        end = span.get("end", span.get("end_position"))
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(text)
        ):
            raise ValueError("AI4Privacy span has invalid offsets")
        entities.append({"type": entity_type, "start": start, "end": end, "text": text[start:end]})
    return {"id": raw.get("id", "ai4privacy"), "text": text, "entities": entities}


def prepare_jsonl(
    *,
    input_path: Path,
    output_path: Path,
    source_format: Literal["hushmark", "ai4privacy"],
    labels: Mapping[str, str],
    limit: int | None = None,
) -> tuple[int, str]:
    """Convert a source JSONL file and return row count plus output digest."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    with (
        input_path.open(encoding="utf-8") as source,
        output_path.open("w", encoding="utf-8") as output,
    ):
        for line_number, line in enumerate(source, start=1):
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError(f"invalid object at line {line_number}")
            normalized = raw if source_format == "hushmark" else normalize_ai4privacy_record(raw)
            if normalized is None:
                continue
            record = prepare_record(normalized, labels, source=source_format)
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            output.write(encoded)
            digest.update(encoded.encode())
            written += 1
            if limit is not None and written >= limit:
                break
    if written == 0:
        raise ValueError("preparation produced no records")
    return written, digest.hexdigest()


def load_prepared(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = json.loads(line)
        if not isinstance(raw, dict) or not isinstance(raw.get("tokenized_text"), list):
            raise ValueError(f"invalid prepared record at line {line_number}")
        if not isinstance(raw.get("ner"), list) or not isinstance(raw.get("ner_labels"), list):
            raise ValueError(f"invalid GLiNER labels at line {line_number}")
        records.append(raw)
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ner_macro_f1(result: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
    per_type = result["strict"]["per_type"]
    scores: dict[str, float] = {}
    for entity_type in NER_TYPES:
        metrics = per_type.get(entity_type)
        if not isinstance(metrics, Mapping) or int(metrics.get("support", 0)) <= 0:
            raise ValueError(f"benchmark result has no support for NER type {entity_type}")
        scores[entity_type] = float(metrics["f1"])
    return sum(scores.values()) / len(scores), scores


def adoption_verdict(
    candidate: Mapping[str, Any],
    incumbent: Mapping[str, Any],
    *,
    eligible: bool,
) -> dict[str, Any]:
    """Apply the binding NER-only improvement and regression rule."""

    candidate_macro, candidate_scores = ner_macro_f1(candidate)
    incumbent_macro, incumbent_scores = ner_macro_f1(incumbent)
    improvement = candidate_macro - incumbent_macro
    regressions = {
        entity_type: incumbent_scores[entity_type] - candidate_scores[entity_type]
        for entity_type in NER_TYPES
        if incumbent_scores[entity_type] - candidate_scores[entity_type] > 0.02
    }
    technical_pass = improvement >= 0.05 and not regressions
    reasons: list[str] = []
    if not eligible:
        reasons.append("checkpoint is smoke-only or evaluation is incomplete")
    if improvement < 0.05:
        reasons.append("NER macro-F1 improvement is below 0.05")
    if regressions:
        reasons.append("one or more NER types regress by more than 0.02 strict-F1")
    if eligible and technical_pass:
        reasons.append("candidate satisfies the adoption rule")
    return {
        "adopt": eligible and technical_pass,
        "eligible": eligible,
        "technical_pass": technical_pass,
        "rule": {
            "minimum_ner_macro_f1_improvement": 0.05,
            "maximum_per_type_strict_f1_regression": 0.02,
        },
        "candidate_ner_macro_f1": candidate_macro,
        "incumbent_ner_macro_f1": incumbent_macro,
        "improvement": improvement,
        "per_type_regressions": dict(sorted(regressions.items())),
        "reasons": reasons,
    }


def json_lines(records: Iterable[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
