"""Decision-grade slices: latency, Turkish morphology, special categories, coverage."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Literal

from hushmark_bench.dataset import deterministic_types
from hushmark_bench.metrics import Counts, evaluate

SPECIAL_CATEGORY_TYPES = frozenset(
    {
        "BIOMETRIC_REF",
        "CRIMINAL",
        "ETHNICITY",
        "HEALTH",
        "POLITICAL",
        "RELIGION",
        "SEXUAL_LIFE",
        "UNION",
    }
)


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(fraction * len(ordered)))
    return ordered[rank - 1]


def latency_summary(durations: Sequence[float]) -> dict[str, float]:
    return {
        "mean_ms": (sum(durations) / len(durations) * 1000.0) if durations else 0.0,
        "p50_ms": percentile(durations, 0.50) * 1000.0,
        "p95_ms": percentile(durations, 0.95) * 1000.0,
        "p99_ms": percentile(durations, 0.99) * 1000.0,
    }


def group_counts(per_type: dict[str, Any], entity_types: frozenset[str]) -> dict[str, int | float]:
    totals = [0, 0, 0, 0]
    for entity_type in entity_types:
        metrics = per_type.get(entity_type)
        if not metrics:
            continue
        totals[0] += int(metrics["true_positive"])
        totals[1] += int(metrics["false_positive"])
        totals[2] += int(metrics["false_negative"])
        totals[3] += int(metrics["support"])
    return Counts(*totals).to_dict()


def coverage(per_type: dict[str, Any]) -> dict[str, Any]:
    """Coverage answers "can this engine see the type at all", so callers pass partial counts."""

    supported = {
        entity_type: metrics for entity_type, metrics in per_type.items() if metrics["support"]
    }
    detected = sorted(
        entity_type for entity_type, metrics in supported.items() if metrics["true_positive"]
    )
    return {
        "types_with_gold": len(supported),
        "types_detected": len(detected),
        "detected": detected,
        "missed": sorted(set(supported) - set(detected)),
    }


def morphology_recall(
    examples: Sequence[dict[str, Any]],
    gold_documents: Sequence[list[dict[str, Any]]],
    predicted_documents: Sequence[list[dict[str, Any]]],
    *,
    mode: Literal["strict", "partial"],
) -> dict[str, dict[str, int | float]]:
    buckets: dict[str, list[int]] = {}
    for index, example in enumerate(examples):
        for morphology in example.get("morphology", ["plain"]):
            buckets.setdefault(str(morphology), []).append(index)
    summary: dict[str, dict[str, int | float]] = {}
    for morphology, indices in sorted(buckets.items()):
        result = evaluate(
            [list(gold_documents[index]) for index in indices],
            [list(predicted_documents[index]) for index in indices],
            mode=mode,
        )
        summary[morphology] = {
            "examples": len(indices),
            **{key: value for key, value in result["micro"].items()},
        }
    return summary


def build_slices(
    examples: Sequence[dict[str, Any]],
    gold_documents: Sequence[list[dict[str, Any]]],
    predicted_documents: Sequence[list[dict[str, Any]]],
    strict: dict[str, Any],
    partial: dict[str, Any],
    durations: Sequence[float],
) -> dict[str, Any]:
    per_type = strict["per_type"]
    return {
        "latency": latency_summary(durations),
        "special_category": group_counts(per_type, SPECIAL_CATEGORY_TYPES),
        "identifier": group_counts(per_type, deterministic_types()),
        "coverage": coverage(partial["per_type"]),
        "morphology": morphology_recall(
            examples, gold_documents, predicted_documents, mode="strict"
        ),
    }
