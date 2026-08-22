"""Reproducible data preparation and adoption rules for hushmark-tr."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Literal

import yaml
from hushmark_core.taxonomy_gen import TAXONOMY

from hushmark_bench.dataset import MORPHOLOGIES, Example, generate_examples, load_dataset
from hushmark_bench.templates import DOMAINS, TEMPLATES

TOKEN_PATTERN = re.compile(r"\w+(?:[-_]\w+)*|\S", re.UNICODE)
BALANCE_UNIT = len(TEMPLATES) * len(MORPHOLOGIES)
DEFAULT_SYNTHETIC_EXAMPLES = math.ceil(200_000 / BALANCE_UNIT) * BALANCE_UNIT
LOCKED_BENCHMARK_REPETITIONS = 8
LOCKED_BENCHMARK_EXAMPLES = len(TEMPLATES) * LOCKED_BENCHMARK_REPETITIONS
DEVELOPMENT_REPETITIONS = 4
DEVELOPMENT_EXAMPLES = len(TEMPLATES) * DEVELOPMENT_REPETITIONS
NER_TYPES = tuple(
    entity_type for entity_type, metadata in TAXONOMY.items() if metadata["layer"] == "ner"
)
AI4PRIVACY_TYPE_ALIASES = {
    "ADDRESS": "ADDRESS",
    "BUILDINGNUM": "ADDRESS",
    "BUILDINGNUMBER": "ADDRESS",
    "CITY": "ADDRESS",
    "COMPANYNAME": "ORG",
    "COUNTY": "ADDRESS",
    "DATEOFBIRTH": "DOB",
    "DOB": "DOB",
    "ETHNICITY": "ETHNICITY",
    "FIRSTNAME": "PERSON",
    "GIVENNAME": "PERSON",
    "HEALTHCONDITION": "HEALTH",
    "LASTNAME": "PERSON",
    "MEDICALCONDITION": "HEALTH",
    "NAME": "PERSON",
    "ORGANIZATION": "ORG",
    "PERSON": "PERSON",
    "STATE": "ADDRESS",
    "STREET": "ADDRESS",
    "SURNAME": "PERSON",
    "ZIPCODE": "ADDRESS",
}


@dataclass(frozen=True, slots=True)
class SynthesisSummary:
    examples: int
    excluded_locked_examples: int
    excluded_development_examples: int
    sha256: str
    domains: dict[str, int]
    morphologies: dict[str, int]
    domain_morphologies: dict[str, int]


def scaled_examples(seed: int, count: int = DEFAULT_SYNTHETIC_EXAMPLES) -> Iterator[Example]:
    """Yield an exactly balanced scaled corpus without retaining it in memory."""

    if count < 200_000 or count % BALANCE_UNIT:
        raise ValueError(f"example count must be >=200000 and divisible by {BALANCE_UNIT}")
    yield from generate_examples(seed, repetitions=count // len(TEMPLATES))


def full_training_examples(seed: int, count: int = DEFAULT_SYNTHETIC_EXAMPLES) -> Iterator[Example]:
    """Yield a balanced corpus strictly after the locked v0 and development rows."""

    if count < 200_000 or count % BALANCE_UNIT:
        raise ValueError(f"example count must be >=200000 and divisible by {BALANCE_UNIT}")
    repetitions = LOCKED_BENCHMARK_REPETITIONS + DEVELOPMENT_REPETITIONS + count // len(TEMPLATES)
    generated = generate_examples(seed, repetitions=repetitions, unique_other_ibans=True)
    first_training_example = LOCKED_BENCHMARK_EXAMPLES + DEVELOPMENT_EXAMPLES
    yield from islice(
        generated,
        first_training_example,
        first_training_example + count,
    )


def development_examples(seed: int) -> Iterator[Example]:
    """Yield the deterministic development range reserved between benchmark and training."""

    repetitions = LOCKED_BENCHMARK_REPETITIONS + DEVELOPMENT_REPETITIONS
    generated = generate_examples(seed, repetitions=repetitions, unique_other_ibans=True)
    yield from islice(
        generated,
        LOCKED_BENCHMARK_EXAMPLES,
        LOCKED_BENCHMARK_EXAMPLES + DEVELOPMENT_EXAMPLES,
    )


def synthesize(
    *,
    seed: int,
    count: int = DEFAULT_SYNTHETIC_EXAMPLES,
    output_path: Path | None = None,
    exclude_locked: bool = False,
) -> SynthesisSummary:
    """Generate canonical JSONL, optionally writing it, and return balance evidence."""

    digest = hashlib.sha256()
    domains: Counter[str] = Counter()
    morphologies: Counter[str] = Counter()
    domain_morphologies: Counter[str] = Counter()
    output = output_path.open("w", encoding="utf-8") if output_path is not None else None
    try:
        examples = (
            full_training_examples(seed, count) if exclude_locked else scaled_examples(seed, count)
        )
        for example in examples:
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
        excluded_locked_examples=LOCKED_BENCHMARK_EXAMPLES if exclude_locked else 0,
        excluded_development_examples=DEVELOPMENT_EXAMPLES if exclude_locked else 0,
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

    # v0 uses the first eight repetitions and development uses the next four. Start
    # after both reserved ranges so smoke training cannot tune either evaluation set.
    first_smoke_example = LOCKED_BENCHMARK_EXAMPLES + DEVELOPMENT_EXAMPLES
    generated = list(
        generate_examples(
            seed,
            repetitions=LOCKED_BENCHMARK_REPETITIONS + DEVELOPMENT_REPETITIONS + 1,
            unique_other_ibans=True,
        )
    )[first_smoke_example : first_smoke_example + 200]
    return [
        prepare_record(asdict(example), labels, source="synthetic-post-benchmark-holdout")
        for example in generated
    ]


def normalize_ai4privacy_record(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize an exported Turkish AI4Privacy JSONL row with character spans."""

    language = raw.get("language", raw.get("lang", raw.get("locale")))
    if isinstance(language, str):
        normalized_language = re.sub(r"[^a-z]", "", language.lower())
        if not (normalized_language.startswith("tr") or normalized_language == "turkish"):
            return None
    text = raw.get("text", raw.get("source_text"))
    spans = raw.get("entities", raw.get("spans", raw.get("privacy_mask")))
    if not isinstance(text, str) or not isinstance(spans, list):
        raise ValueError("AI4Privacy row requires text/source_text and entities/spans/privacy_mask")
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
        supplied_value = span.get("value", span.get("text"))
        if supplied_value is not None and supplied_value != text[start:end]:
            raise ValueError("AI4Privacy span value does not match its offsets")
        entities.append({"type": entity_type, "start": start, "end": end, "text": text[start:end]})
    return {
        "id": raw.get("id", raw.get("uid", "ai4privacy")),
        "text": text,
        "entities": entities,
    }


def prepare_jsonl(
    *,
    input_path: Path,
    output_path: Path,
    source_format: Literal["hushmark", "synthetic-full", "synthetic-dev", "ai4privacy"],
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
            normalized = normalize_ai4privacy_record(raw) if source_format == "ai4privacy" else raw
            if normalized is None:
                continue
            record_source = "hushmark-bench-v0" if source_format == "hushmark" else source_format
            record = prepare_record(normalized, labels, source=record_source)
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
        tokens = raw["tokenized_text"]
        labels = raw["ner_labels"]
        if not all(isinstance(token, str) and token for token in tokens):
            raise ValueError(f"invalid prepared tokens at line {line_number}")
        if not all(isinstance(label, str) and label for label in labels):
            raise ValueError(f"invalid prepared label names at line {line_number}")
        for span in raw["ner"]:
            if (
                not isinstance(span, list)
                or len(span) != 3
                or not isinstance(span[0], int)
                or not isinstance(span[1], int)
                or not isinstance(span[2], str)
                or not 0 <= span[0] <= span[1] < len(tokens)
                or span[2] not in labels
            ):
                raise ValueError(f"invalid prepared span at line {line_number}")
        records.append(raw)
    if not records:
        raise ValueError("prepared dataset is empty")
    return records


def prepared_required_max_width(records: Iterable[Mapping[str, Any]]) -> int:
    """Return the widest inclusive gold span in a prepared GLiNER corpus."""

    maximum = 1
    seen = False
    for record in records:
        spans = record.get("ner")
        if not isinstance(spans, list):
            raise ValueError("prepared record has invalid NER spans")
        for span in spans:
            if (
                not isinstance(span, list)
                or len(span) != 3
                or not isinstance(span[0], int)
                or not isinstance(span[1], int)
                or span[0] > span[1]
            ):
                raise ValueError("prepared record has an invalid token span")
            maximum = max(maximum, span[1] - span[0] + 1)
            seen = True
    return maximum if seen else 1


def load_validation_examples(path: Path, labels: Mapping[str, str]) -> list[dict[str, Any]]:
    """Load raw character spans or reconstruct them from prepared GLiNER rows.

    Prepared rows do not necessarily retain original whitespace. Reconstructing
    with one space between tokens keeps every gold token span exact and makes the
    documented prepared validation path usable for checkpoint selection.
    """

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("validation dataset is empty")
    first = json.loads(lines[0])
    if isinstance(first, dict) and isinstance(first.get("text"), str):
        return load_dataset(path)

    prepared = load_prepared(path)
    label_to_type = {label: entity_type for entity_type, label in labels.items()}
    examples: list[dict[str, Any]] = []
    for line_number, record in enumerate(prepared, start=1):
        tokens = record["tokenized_text"]
        starts: list[int] = []
        cursor = 0
        for token in tokens:
            starts.append(cursor)
            cursor += len(token) + 1
        text = " ".join(tokens)
        entities: list[dict[str, Any]] = []
        for first_token, last_token, model_label in record["ner"]:
            entity_type = label_to_type.get(model_label)
            if entity_type is None:
                raise ValueError(
                    f"prepared validation label {model_label!r} at line {line_number} "
                    "is not part of the configured Hushmark taxonomy"
                )
            start = starts[first_token]
            end = starts[last_token] + len(tokens[last_token])
            entities.append(
                {
                    "type": entity_type,
                    "start": start,
                    "end": end,
                    "text": text[start:end],
                }
            )
        examples.append(
            {
                "id": str(record.get("id", f"prepared-validation-{line_number}")),
                "text": text,
                "entities": entities,
            }
        )
    return examples


def resolve_training_max_width(
    model_dir: Path,
    records: Iterable[Mapping[str, Any]],
    *,
    requested: int | None,
) -> tuple[int, int]:
    """Choose a lossless max width for the pinned span architecture."""

    config = json.loads((model_dir / "gliner_config.json").read_text(encoding="utf-8"))
    configured = config.get("max_width")
    if not isinstance(configured, int) or configured < 1:
        raise ValueError("base model has an invalid max_width")
    required = prepared_required_max_width(records)
    effective = max(configured, required) if requested is None else requested
    if effective < required:
        raise ValueError(
            f"max_width={effective} cannot represent the widest gold span ({required} tokens)"
        )
    if effective < 1:
        raise ValueError("max_width must be positive")
    if effective != configured and config.get("span_mode") != "markerV0":
        raise ValueError(
            "automatic max_width expansion is supported only for the pinned markerV0 architecture"
        )
    return effective, required


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepared_record_fingerprint(record: Mapping[str, Any]) -> str:
    """Hash only model-visible content so renamed evaluation rows are still detected."""

    payload = {
        "tokenized_text": record.get("tokenized_text"),
        "ner": record.get("ner"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def assert_evaluation_isolation(
    training_records: Iterable[Mapping[str, Any]],
    evaluation_records: Iterable[Mapping[str, Any]],
) -> None:
    """Reject source, id, or model-visible content overlap with locked evaluation data."""

    evaluation = list(evaluation_records)
    evaluation_ids = {str(record.get("id")) for record in evaluation}
    evaluation_fingerprints = {prepared_record_fingerprint(record) for record in evaluation}
    for record in training_records:
        if record.get("source") == "hushmark-bench-v0":
            raise ValueError("training data contains the locked evaluation source")
        if str(record.get("id")) in evaluation_ids:
            raise ValueError("training data contains a locked evaluation record id")
        if prepared_record_fingerprint(record) in evaluation_fingerprints:
            raise ValueError("training data contains locked evaluation content")


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


def supplemental_adoption_verdict(
    candidate: Mapping[str, Any],
    incumbent: Mapping[str, Any],
    *,
    entity_types: Iterable[str],
    eligible: bool,
    minimum_macro_f1_improvement: float = 0.05,
    maximum_per_type_regression: float = 0.02,
    maximum_empty_gold_fp_increase: int = 0,
) -> dict[str, Any]:
    """Gate a new-data holdout without weakening the legacy locked-benchmark rule."""

    scoped_types = tuple(sorted(set(entity_types)))
    if not scoped_types or not set(scoped_types).issubset(NER_TYPES):
        raise ValueError("supplemental gate requires supported closed-taxonomy NER types")

    def scores(report: Mapping[str, Any]) -> dict[str, float]:
        per_type = report["strict"]["per_type"]
        result: dict[str, float] = {}
        for entity_type in scoped_types:
            metrics = per_type.get(entity_type)
            if not isinstance(metrics, Mapping) or int(metrics.get("support", 0)) <= 0:
                raise ValueError(f"supplemental result has no support for {entity_type}")
            result[entity_type] = float(metrics["f1"])
        return result

    candidate_scores = scores(candidate)
    incumbent_scores = scores(incumbent)
    candidate_macro = sum(candidate_scores.values()) / len(candidate_scores)
    incumbent_macro = sum(incumbent_scores.values()) / len(incumbent_scores)
    improvement = candidate_macro - incumbent_macro
    regressions = {
        entity_type: incumbent_scores[entity_type] - candidate_scores[entity_type]
        for entity_type in scoped_types
        if incumbent_scores[entity_type] - candidate_scores[entity_type]
        > maximum_per_type_regression
    }
    candidate_empty_fp = int(candidate["empty_gold"]["false_positive_spans"])
    incumbent_empty_fp = int(incumbent["empty_gold"]["false_positive_spans"])
    empty_fp_increase = candidate_empty_fp - incumbent_empty_fp
    technical_pass = (
        improvement >= minimum_macro_f1_improvement
        and not regressions
        and empty_fp_increase <= maximum_empty_gold_fp_increase
    )
    reasons: list[str] = []
    if not eligible:
        reasons.append("legacy locked-benchmark verdict did not authorize adoption")
    if improvement < minimum_macro_f1_improvement:
        reasons.append("new-holdout NER macro-F1 improvement is below the required minimum")
    if regressions:
        reasons.append("one or more new-holdout NER types regress beyond the allowed limit")
    if empty_fp_increase > maximum_empty_gold_fp_increase:
        reasons.append("false-positive spans on empty-gold documents increased")
    if eligible and technical_pass:
        reasons.append("candidate satisfies both legacy and new-holdout adoption gates")
    return {
        "adopt": eligible and technical_pass,
        "eligible": eligible,
        "technical_pass": technical_pass,
        "entity_types": list(scoped_types),
        "rule": {
            "minimum_ner_macro_f1_improvement": minimum_macro_f1_improvement,
            "maximum_per_type_strict_f1_regression": maximum_per_type_regression,
            "maximum_empty_gold_false_positive_span_increase": maximum_empty_gold_fp_increase,
        },
        "candidate_ner_macro_f1": candidate_macro,
        "incumbent_ner_macro_f1": incumbent_macro,
        "improvement": improvement,
        "per_type_regressions": dict(sorted(regressions.items())),
        "candidate_empty_gold_false_positive_spans": candidate_empty_fp,
        "incumbent_empty_gold_false_positive_spans": incumbent_empty_fp,
        "empty_gold_false_positive_span_increase": empty_fp_increase,
        "reasons": reasons,
    }


def json_lines(records: Iterable[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
