from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
from hushmark_bench.training import (
    DEVELOPMENT_EXAMPLES,
    NER_TYPES,
    adoption_verdict,
    assert_evaluation_isolation,
    development_examples,
    full_training_examples,
    load_model_labels,
    load_validation_examples,
    normalize_ai4privacy_record,
    prepare_hushmark_records,
    prepare_jsonl,
    prepare_record,
    prepared_required_max_width,
    resolve_training_max_width,
    smoke_records,
    supplemental_adoption_verdict,
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


def test_full_synthesis_excludes_locked_benchmark_and_remains_balanced() -> None:
    first = synthesize(seed=20260809, count=200_592, exclude_locked=True)
    second = synthesize(seed=20260809, count=200_592, exclude_locked=True)
    examples = list(full_training_examples(seed=20260809, count=200_592))
    benchmark_ids = {
        json.loads(line)["id"]
        for line in (ROOT / "bench/data/hushmark-bench-v0.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert first == second
    assert first.excluded_locked_examples == 2016
    assert first.excluded_development_examples == DEVELOPMENT_EXAMPLES
    assert len(examples) == 200_592
    assert not ({example.id for example in examples} & benchmark_ids)
    assert len(set(first.domains.values())) == 1
    assert len(set(first.domain_morphologies.values())) == 1
    labels = load_model_labels(ROOT / "core/models.yaml")
    evaluation = prepare_hushmark_records(ROOT / "bench/data/hushmark-bench-v0.jsonl", labels)
    development = [
        prepare_record(asdict(example), labels, source="synthetic-dev")
        for example in development_examples(20260809)
    ]
    assert len(development) == DEVELOPMENT_EXAMPLES
    assert_evaluation_isolation(development, evaluation)
    assert_evaluation_isolation(
        (prepare_record(asdict(example), labels, source="synthetic-full") for example in examples),
        evaluation,
    )
    assert_evaluation_isolation(
        (prepare_record(asdict(example), labels, source="synthetic-full") for example in examples),
        development,
    )


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
    development_ids = {example.id for example in development_examples(20260809)}
    assert not ({record["id"] for record in records} & development_ids)


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


def test_ai4privacy_openpii_schema_and_current_aliases(tmp_path: Path) -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    source = tmp_path / "openpii.jsonl"
    output = tmp_path / "prepared.jsonl"
    text = "Deniz Yılmaz, 42 numarada oturuyor"
    rows = [
        {
            "uid": "openpii-tr-1",
            "language": "Turkish",
            "source_text": text,
            "privacy_mask": [
                {"start": 0, "end": 5, "label": "GIVENNAME", "value": "Deniz"},
                {"start": 6, "end": 12, "label": "SURNAME", "value": "Yılmaz"},
                {"start": 14, "end": 16, "label": "BUILDINGNUM", "value": "42"},
            ],
        }
    ]
    source.write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
    count, _ = prepare_jsonl(
        input_path=source,
        output_path=output,
        source_format="ai4privacy",
        labels=labels,
    )
    prepared = json.loads(output.read_text(encoding="utf-8"))
    assert count == 1
    assert prepared["id"] == "openpii-tr-1"
    assert prepared["source"] == "ai4privacy"
    assert prepared["ner"] == [
        [0, 0, "person"],
        [1, 1, "person"],
        [3, 3, "full address"],
    ]


def test_evaluation_isolation_detects_renamed_content() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    evaluation = prepare_hushmark_records(ROOT / "bench/data/hushmark-bench-v0.jsonl", labels)
    renamed = dict(evaluation[0], id="renamed", source="external")
    with pytest.raises(ValueError, match="evaluation content"):
        assert_evaluation_isolation([renamed], evaluation)

    first_full = next(full_training_examples(seed=20260809, count=200_592))
    prepared_full = prepare_record(asdict(first_full), labels, source="synthetic-full")
    assert_evaluation_isolation([prepared_full], evaluation)


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


def test_supplemental_adoption_gate_requires_gain_and_no_new_negative_fp() -> None:
    def report(scores: dict[str, float], false_positives: int) -> dict[str, Any]:
        return {
            "strict": {
                "per_type": {
                    entity_type: {"support": 1, "f1": score}
                    for entity_type, score in scores.items()
                }
            },
            "empty_gold": {"false_positive_spans": false_positives},
        }

    types = ("PERSON", "ADDRESS", "DOB")
    incumbent = report(dict.fromkeys(types, 0.50), 4)
    passing = supplemental_adoption_verdict(
        report(dict.fromkeys(types, 0.56), 4), incumbent, entity_types=types, eligible=True
    )
    assert passing["adopt"] is True

    noisier = supplemental_adoption_verdict(
        report(dict.fromkeys(types, 0.60), 5), incumbent, entity_types=types, eligible=True
    )
    assert noisier["technical_pass"] is False
    assert noisier["empty_gold_false_positive_span_increase"] == 1


def test_ai4privacy_adapter_rejects_bad_offsets() -> None:
    with pytest.raises(ValueError, match="invalid offsets"):
        normalize_ai4privacy_record(
            {
                "language": "tr",
                "text": "Deniz",
                "entities": [{"start": 2, "end": 20, "label": "FIRSTNAME"}],
            }
        )


def test_ai4privacy_adapter_rejects_mismatched_value() -> None:
    with pytest.raises(ValueError, match="does not match"):
        normalize_ai4privacy_record(
            {
                "language": "tr",
                "source_text": "Deniz",
                "privacy_mask": [{"start": 0, "end": 5, "label": "GIVENNAME", "value": "Ayşe"}],
            }
        )


def test_prepared_validation_is_reconstructed_with_exact_gold_offsets(tmp_path: Path) -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    path = tmp_path / "validation.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "prepared-1",
                "source": "test",
                "tokenized_text": ["Ayşe", "Yılmaz", "Ankara", "'", "da"],
                "ner": [[0, 1, "person"], [2, 4, "full address"]],
                "ner_labels": list(labels.values()),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    examples = load_validation_examples(path, labels)
    assert examples == [
        {
            "id": "prepared-1",
            "text": "Ayşe Yılmaz Ankara ' da",
            "entities": [
                {"type": "PERSON", "start": 0, "end": 11, "text": "Ayşe Yılmaz"},
                {"type": "ADDRESS", "start": 12, "end": 23, "text": "Ankara ' da"},
            ],
        }
    ]


def test_training_width_expands_losslessly_for_marker_v0(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "gliner_config.json").write_text(
        json.dumps({"max_width": 12, "span_mode": "markerV0"}),
        encoding="utf-8",
    )
    records = [
        {
            "tokenized_text": [str(index) for index in range(16)],
            "ner": [[0, 15, "full address"]],
            "ner_labels": ["full address"],
        }
    ]
    assert prepared_required_max_width(records) == 16
    assert resolve_training_max_width(model_dir, records, requested=None) == (16, 16)
    with pytest.raises(ValueError, match="widest gold span"):
        resolve_training_max_width(model_dir, records, requested=12)
