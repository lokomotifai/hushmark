from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from hushmark_bench.training import NER_TYPES, development_examples, load_model_labels
from hushmark_bench.validation import (
    validate_ner_model,
    validate_ner_model_batched,
    validate_ner_suites,
    validate_ner_thresholds,
    validation_rank,
)

ROOT = Path(__file__).resolve().parents[2]


class GoldModel:
    def __init__(self, examples: list[dict[str, Any]], labels: dict[str, str]) -> None:
        self._labels = labels
        self._by_text = {example["text"]: example["entities"] for example in examples}

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, object]]:
        assert set(labels) == set(self._labels.values())
        return [
            {
                "start": entity["start"],
                "end": entity["end"],
                "label": self._labels[entity["type"]],
                "score": max(threshold, 0.99),
            }
            for entity in self._by_text[text]
            if entity["type"] in NER_TYPES
        ]


def test_development_validation_scores_only_ner_types() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    examples = [asdict(example) for example in development_examples(20260809)]
    report = validate_ner_model(GoldModel(examples, labels), examples, labels, threshold=0.5)
    assert report["examples"] == len(examples)
    assert report["ner_macro_f1"] == 1.0
    assert set(report["strict"]["per_type"]) == set(NER_TYPES)
    assert report["partial"]["micro"]["f1"] == 1.0
    assert report["empty_gold"] == {
        "documents": sum(
            not any(entity["type"] in NER_TYPES for entity in example["entities"])
            for example in examples
        ),
        "documents_with_false_positives": 0,
        "false_positive_spans": 0,
    }


def test_validation_suites_preserve_domain_reports_and_combine_counts() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")
    legacy = [asdict(example) for example in development_examples(20260809)]
    new = [
        {
            "text": "Yeni örnek: Ayşe",
            "entities": [{"type": "PERSON", "start": 12, "end": 16, "text": "Ayşe"}],
        }
    ]
    examples = [*legacy, *new]
    report = validate_ner_suites(
        GoldModel(examples, labels),
        {"legacy": legacy, "new": new},
        labels,
        threshold=0.5,
    )
    assert report["examples"] == len(examples)
    assert report["ner_macro_f1"] == 1.0
    assert report["suites"]["new"]["supported_types"] == ["PERSON"]
    assert report["strict"]["per_type"]["PERSON"]["support"] == (
        report["suites"]["legacy"]["strict"]["per_type"]["PERSON"]["support"] + 1
    )


def test_validation_rank_prefers_technical_pass_before_raw_macro() -> None:
    passing = {
        "verdict": {
            "technical_pass": True,
            "candidate_ner_macro_f1": 0.4,
            "per_type_regressions": {},
        }
    }
    failing = {
        "verdict": {
            "technical_pass": False,
            "candidate_ner_macro_f1": 0.9,
            "per_type_regressions": {"PERSON": 0.1},
        }
    }
    assert validation_rank(passing) > validation_rank(failing)


def test_validate_thresholds_reuses_one_inference_pass() -> None:
    class ScoredModel:
        calls = 0

        def __init__(self, label_by_text: dict[str, str]) -> None:
            self.label_by_text = label_by_text

        def predict_entities(self, text, labels, threshold):
            self.calls += 1
            assert threshold == 0.1
            return [
                {"label": self.label_by_text[text], "start": 0, "end": 3, "score": 0.8},
                {"label": self.label_by_text[text], "start": 4, "end": 7, "score": 0.2},
            ]

    label_by_type = {entity_type: f"label-{entity_type.lower()}" for entity_type in NER_TYPES}
    model = ScoredModel(label_by_type)
    reports = validate_ner_thresholds(
        model,
        [
            {
                "text": entity_type,
                "entities": [{"type": entity_type, "start": 0, "end": 3}],
            }
            for entity_type in NER_TYPES
        ],
        label_by_type,
        thresholds=[0.5, 0.1],
    )

    assert model.calls == len(NER_TYPES)
    assert [report["threshold"] for report in reports] == [0.1, 0.5]
    assert reports[0]["strict"]["micro"]["false_positive"] == len(NER_TYPES)
    assert reports[1]["strict"]["micro"]["f1"] == 1.0


def test_validate_batched_uses_one_model_call() -> None:
    label_by_type = {entity_type: f"label-{entity_type.lower()}" for entity_type in NER_TYPES}

    class BatchModel:
        calls = 0

        def inference(self, texts, labels, *, threshold, batch_size):
            self.calls += 1
            assert threshold == 0.4
            assert batch_size == 8
            return [
                [
                    {
                        "label": label_by_type[text],
                        "start": 0,
                        "end": 3,
                        "score": 0.9,
                    }
                ]
                for text in texts
            ]

    examples = [
        {
            "text": entity_type,
            "entities": [{"type": entity_type, "start": 0, "end": 3}],
        }
        for entity_type in NER_TYPES
    ]
    model = BatchModel()
    report = validate_ner_model_batched(
        model,
        examples,
        label_by_type,
        threshold=0.4,
        batch_size=8,
    )

    assert model.calls == 1
    assert report["ner_macro_f1"] == 1.0
    assert report["empty_gold"] == {
        "documents": 0,
        "documents_with_false_positives": 0,
        "false_positive_spans": 0,
    }


def test_validate_batched_allows_a_supported_taxonomy_subset() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")

    class PersonModel:
        def inference(self, texts, model_labels, *, threshold, batch_size):
            assert set(model_labels) == set(labels.values())
            return [[{"label": labels["PERSON"], "start": 0, "end": 4, "score": 0.9}]]

    report = validate_ner_model_batched(
        PersonModel(),
        [{"text": "Ayşe", "entities": [{"type": "PERSON", "start": 0, "end": 4}]}],
        labels,
        threshold=0.4,
        batch_size=8,
    )
    assert report["strict"]["per_type"]["PERSON"]["support"] == 1
    assert report["ner_macro_f1"] == 1.0


def test_validate_batched_counts_empty_gold_false_positives() -> None:
    labels = load_model_labels(ROOT / "core/models.yaml")

    class NoisyModel:
        def inference(self, texts, model_labels, *, threshold, batch_size):
            return [[{"label": labels["PERSON"], "start": 0, "end": 4, "score": 0.9}]]

    report = validate_ner_model_batched(
        NoisyModel(),
        [{"text": "Ayşe", "entities": []}],
        labels,
        threshold=0.4,
        batch_size=8,
    )
    assert report["empty_gold"] == {
        "documents": 1,
        "documents_with_false_positives": 1,
        "false_positive_spans": 1,
    }
