"""Strict and partial span metrics with per-type and macro summaries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Counts:
    true_positive: int
    false_positive: int
    false_negative: int
    support: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        return self.true_positive / self.support if self.support else 0.0

    @property
    def f1(self) -> float:
        total = self.precision + self.recall
        return 2 * self.precision * self.recall / total if total else 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            **asdict(self),
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


def spans_match(
    gold: dict[str, Any], predicted: dict[str, Any], mode: Literal["strict", "partial"]
) -> bool:
    if gold["type"] != predicted["type"]:
        return False
    gold_start = int(gold["start"])
    gold_end = int(gold["end"])
    predicted_start = int(predicted["start"])
    predicted_end = int(predicted["end"])
    if mode == "strict":
        return gold_start == predicted_start and gold_end == predicted_end
    return gold_start < predicted_end and predicted_start < gold_end


def evaluate(
    gold_documents: list[list[dict[str, Any]]],
    predicted_documents: list[list[dict[str, Any]]],
    *,
    mode: Literal["strict", "partial"],
) -> dict[str, Any]:
    if len(gold_documents) != len(predicted_documents):
        raise ValueError("gold and predicted document counts differ")
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for gold_entities, predicted_entities in zip(gold_documents, predicted_documents, strict=True):
        types = {entity["type"] for entity in gold_entities + predicted_entities}
        for entity_type in types:
            gold = [entity for entity in gold_entities if entity["type"] == entity_type]
            predicted = [entity for entity in predicted_entities if entity["type"] == entity_type]
            matched_predictions: set[int] = set()
            true_positive = 0
            for gold_entity in gold:
                candidates = [
                    index
                    for index, predicted_entity in enumerate(predicted)
                    if index not in matched_predictions
                    and spans_match(gold_entity, predicted_entity, mode)
                ]
                if candidates:
                    matched_predictions.add(candidates[0])
                    true_positive += 1
            totals[entity_type][0] += true_positive
            totals[entity_type][1] += len(predicted) - true_positive
            totals[entity_type][2] += len(gold) - true_positive
            totals[entity_type][3] += len(gold)
    per_type = {
        entity_type: Counts(*values).to_dict() for entity_type, values in sorted(totals.items())
    }
    supported = [metrics for metrics in per_type.values() if metrics["support"]]
    macro = {
        metric: sum(float(values[metric]) for values in supported) / len(supported)
        if supported
        else 0.0
        for metric in ("precision", "recall", "f1")
    }
    aggregate = [sum(values[index] for values in totals.values()) for index in range(4)]
    return {
        "mode": mode,
        "per_type": per_type,
        "macro": macro,
        "micro": Counts(*aggregate).to_dict(),
    }
