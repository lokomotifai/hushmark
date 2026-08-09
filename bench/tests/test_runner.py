from __future__ import annotations

import pytest
from hushmark_bench.dataset import deterministic_types
from hushmark_bench.runner import enforce_l0_gate


def passing_metrics() -> dict[str, object]:
    return {
        "per_type": {
            entity_type: {"support": 1, "precision": 1.0, "recall": 1.0}
            for entity_type in deterministic_types()
        }
    }


def test_l0_gate_accepts_complete_perfect_metrics() -> None:
    enforce_l0_gate(passing_metrics())


def test_l0_gate_rejects_recall_below_contract() -> None:
    metrics = passing_metrics()
    per_type = metrics["per_type"]
    assert isinstance(per_type, dict)
    per_type["TR_TCKN"]["recall"] = 0.98
    with pytest.raises(RuntimeError, match="TR_TCKN"):
        enforce_l0_gate(metrics)
