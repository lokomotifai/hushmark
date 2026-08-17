"""Slice metric behaviour: latency percentiles, grouping, coverage, morphology."""

from __future__ import annotations

import pytest
from hushmark_bench.metrics import evaluate
from hushmark_bench.slices import (
    SPECIAL_CATEGORY_TYPES,
    build_slices,
    coverage,
    group_counts,
    latency_summary,
    morphology_recall,
    percentile,
)


def span(entity_type: str, start: int, end: int) -> dict[str, object]:
    return {"type": entity_type, "start": start, "end": end}


def test_percentile_uses_nearest_rank() -> None:
    values = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert percentile(values, 0.5) == 0.3
    assert percentile(values, 0.95) == 0.5
    assert percentile([], 0.5) == 0.0


def test_latency_summary_reports_milliseconds() -> None:
    summary = latency_summary([0.001, 0.002, 0.003])
    assert summary["p50_ms"] == pytest.approx(2.0)
    assert summary["mean_ms"] == pytest.approx(2.0)


def test_group_counts_aggregates_only_requested_types() -> None:
    per_type = {
        "HEALTH": {"true_positive": 1, "false_positive": 0, "false_negative": 1, "support": 2},
        "EMAIL": {"true_positive": 5, "false_positive": 0, "false_negative": 0, "support": 5},
    }
    grouped = group_counts(per_type, SPECIAL_CATEGORY_TYPES)
    assert grouped["support"] == 2
    assert grouped["recall"] == pytest.approx(0.5)


def test_coverage_separates_detected_from_missed() -> None:
    per_type = {
        "EMAIL": {"true_positive": 1, "false_positive": 0, "false_negative": 0, "support": 1},
        "HEALTH": {"true_positive": 0, "false_positive": 0, "false_negative": 2, "support": 2},
        "UNUSED": {"true_positive": 0, "false_positive": 3, "false_negative": 0, "support": 0},
    }
    result = coverage(per_type)
    assert result["types_with_gold"] == 2
    assert result["detected"] == ["EMAIL"]
    assert result["missed"] == ["HEALTH"]


def test_morphology_recall_splits_by_declared_bucket() -> None:
    examples = [
        {"morphology": ["plain"], "text": "a"},
        {"morphology": ["missing_diacritics"], "text": "b"},
    ]
    gold = [[span("EMAIL", 0, 1)], [span("EMAIL", 0, 1)]]
    predicted = [[span("EMAIL", 0, 1)], []]
    summary = morphology_recall(examples, gold, predicted, mode="strict")
    assert summary["plain"]["recall"] == pytest.approx(1.0)
    assert summary["missing_diacritics"]["recall"] == pytest.approx(0.0)
    assert summary["plain"]["examples"] == 1


def test_build_slices_covers_every_section() -> None:
    examples = [{"morphology": ["plain"], "text": "a"}]
    gold = [[span("TR_TCKN", 0, 11), span("HEALTH", 12, 20)]]
    predicted = [[span("TR_TCKN", 0, 11)]]
    strict = evaluate(gold, predicted, mode="strict")
    partial = evaluate(gold, predicted, mode="partial")
    slices = build_slices(examples, gold, predicted, strict, partial, [0.01])
    assert slices["identifier"]["recall"] == pytest.approx(1.0)
    assert slices["special_category"]["recall"] == pytest.approx(0.0)
    assert slices["coverage"]["types_detected"] == 1
    assert slices["latency"]["p95_ms"] == pytest.approx(10.0)
