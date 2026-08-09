from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hushmark_bench.training import (
    NER_TYPES,
    adoption_verdict,
    load_model_labels,
    normalize_ai4privacy_record,
    prepare_jsonl,
    prepare_record,
    smoke_records,
    synthesize,
)

ROOT = Path(__file__).resolve().parents[2]


def result_with_scores(scores: dict[str, float]) -> dict[str, Any]:
    return {
        "strict": {
            "per_type": {
                entity_type: {"support": 1, "f1": scores[entity_type]} for entity_type in NER_TYPES
            }
        }
    }


def test_scaled_synthesis_is_balanced_and_deterministic() -> None:
    first = synthesize(seed=20260809, count=200_592)
    second = synthesize(seed=20260809, count=200_592)
    assert first == second
    assert first.examples >= 200_000
    assert len(set(first.domains.values())) == 1
    assert len(set(first.domain_morphologies.values())) == 1


def test_smoke_records_do_not_overlap_locked_benchmark() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    records = smoke_records(20260809, labels)
    benchmark_ids = {
        json.loads(line)["id"]
        for line in (ROOT / "bench/data/hushmark-bench-v0.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert len(records) == 200
    assert {record["source"] for record in records} == {"synthetic-post-benchmark-holdout"}
    assert not ({record["id"] for record in records} & benchmark_ids)


def test_prepare_record_preserves_turkish_token_span() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    text = "Ayşe Yılmaz'ın kaydı"
    raw = {
        "id": "tr-1",
        "text": text,
        "entities": [{"type": "PERSON", "start": 0, "end": 14, "text": text[:14]}],
    }
    record = prepare_record(raw, labels, source="test")
    assert record["tokenized_text"][:4] == ["Ayşe", "Yılmaz", "'", "ın"]
    assert record["ner"] == [[0, 3, "person"]]


def test_ai4privacy_adapter_filters_language_and_converts_alias(tmp_path: Path) -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    source = tmp_path / "source.jsonl"
    output = tmp_path / "prepared.jsonl"
    rows = [
        {
            "id": "tr",
            "language": "tr",
            "text": "Deniz geldi",
            "entities": [{"start": 0, "end": 5, "label": "FIRSTNAME"}],
        },
        {
            "id": "en",
            "language": "en",
            "text": "Alex arrived",
            "entities": [{"start": 0, "end": 4, "label": "FIRSTNAME"}],
        },
    ]
    source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    count, digest = prepare_jsonl(
        input_path=source,
        output_path=output,
        source_format="ai4privacy",
        labels=labels,
    )
    prepared = json.loads(output.read_text(encoding="utf-8"))
    assert count == 1
    assert len(digest) == 64
    assert prepared["ner"] == [[0, 0, "person"]]
    assert normalize_ai4privacy_record(rows[1]) is None


def test_adoption_rule_requires_gain_no_regression_and_eligibility() -> None:
    incumbent_scores = dict.fromkeys(NER_TYPES, 0.50)
    passing_scores = dict.fromkeys(NER_TYPES, 0.56)
    passing = adoption_verdict(
        result_with_scores(passing_scores),
        result_with_scores(incumbent_scores),
        eligible=True,
    )
    assert passing["adopt"] is True

    passing_scores[NER_TYPES[0]] = 0.47
    regressed = adoption_verdict(
        result_with_scores(passing_scores),
        result_with_scores(incumbent_scores),
        eligible=True,
    )
    assert regressed["adopt"] is False
    assert NER_TYPES[0] in regressed["per_type_regressions"]

    smoke = adoption_verdict(
        result_with_scores(dict.fromkeys(NER_TYPES, 0.80)),
        result_with_scores(incumbent_scores),
        eligible=False,
    )
    assert smoke["technical_pass"] is True
    assert smoke["adopt"] is False


def test_ai4privacy_adapter_rejects_bad_offsets() -> None:
    with pytest.raises(ValueError, match="invalid offsets"):
        normalize_ai4privacy_record(
            {
                "language": "tr",
                "text": "Deniz",
                "entities": [{"start": 2, "end": 20, "label": "FIRSTNAME"}],
            }
        )
