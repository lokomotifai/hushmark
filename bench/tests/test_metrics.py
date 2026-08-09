from __future__ import annotations

import pytest
from hushmark_bench.metrics import Counts, evaluate


def entity(entity_type: str, start: int, end: int) -> dict[str, object]:
    return {"type": entity_type, "start": start, "end": end}


def test_strict_and_partial_span_metrics_diverge_on_overlap() -> None:
    gold = [[entity("PERSON", 4, 14)]]
    predicted = [[entity("PERSON", 4, 12)]]
    strict = evaluate(gold, predicted, mode="strict")["per_type"]["PERSON"]
    partial = evaluate(gold, predicted, mode="partial")["per_type"]["PERSON"]
    assert strict["f1"] == 0.0
    assert partial["f1"] == 1.0


def test_prediction_can_match_at_most_one_gold_span() -> None:
    gold = [[entity("PERSON", 0, 4), entity("PERSON", 4, 8)]]
    predicted = [[entity("PERSON", 0, 8)]]
    metrics = evaluate(gold, predicted, mode="partial")["per_type"]["PERSON"]
    assert metrics["true_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["false_positive"] == 0


def test_type_mismatch_counts_false_positive_and_false_negative() -> None:
    metrics = evaluate(
        [[entity("PERSON", 0, 4)]],
        [[entity("ORG", 0, 4)]],
        mode="strict",
    )["per_type"]
    assert metrics["PERSON"]["false_negative"] == 1
    assert metrics["ORG"]["false_positive"] == 1


def test_counts_zero_denominators_are_explicit_zero() -> None:
    counts = Counts(0, 0, 0, 0)
    assert counts.precision == counts.recall == counts.f1 == 0.0


def test_document_count_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="counts differ"):
        evaluate([[]], [], mode="strict")
