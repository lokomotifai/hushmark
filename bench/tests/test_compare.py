"""Comparison rendering: ordering, criteria columns, and missing-slice tolerance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from hushmark_bench.compare import load_results, render_comparison


def result_fixture(engine: str, recall: float, *, backend: str = "onnx") -> dict[str, Any]:
    counts = {
        "true_positive": int(recall * 10),
        "false_positive": 0,
        "false_negative": 10 - int(recall * 10),
        "support": 10,
        "precision": 1.0,
        "recall": recall,
        "f1": recall,
    }
    return {
        "schema_version": 1,
        "engine": engine,
        "backend": backend,
        "model_id": f"{engine}-model",
        "model_sha256": None,
        "dataset": {"name": "d.jsonl", "examples": 2, "sha256": "abc"},
        "duration_seconds": 1.0,
        "strict": {"mode": "strict", "per_type": {"EMAIL": counts}, "macro": {}, "micro": counts},
        "partial": {"mode": "partial", "per_type": {"EMAIL": counts}, "macro": {}, "micro": counts},
        "slices": {
            "latency": {"mean_ms": 1.0, "p50_ms": 1.0, "p95_ms": 2.0, "p99_ms": 3.0},
            "special_category": counts,
            "identifier": counts,
            "coverage": {"types_with_gold": 2, "types_detected": 1, "detected": [], "missed": []},
            "morphology": {"plain": {"examples": 2, **counts}},
        },
    }


def write_results(directory: Path, results: list[dict[str, Any]]) -> Path:
    report_path = directory / "compare.md"
    for result in results:
        target = directory / f"compare-{result['engine']}.json"
        target.write_text(json.dumps(result), encoding="utf-8")
    return report_path


def test_load_results_orders_by_strict_recall(tmp_path: Path) -> None:
    report_path = write_results(
        tmp_path,
        [result_fixture("alpha", 0.2), result_fixture("beta", 0.8)],
    )
    assert [result["engine"] for result in load_results(report_path)] == ["beta", "alpha"]


def test_load_results_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no benchmark engine results"):
        load_results(tmp_path / "compare.md")


def test_render_comparison_writes_every_section(tmp_path: Path) -> None:
    report_path = write_results(
        tmp_path,
        [result_fixture("core", 0.9), result_fixture("openai-llm", 0.5, backend="api")],
    )
    output = tmp_path / "out.md"
    render_comparison(report_path, output)
    rendered = output.read_text(encoding="utf-8")
    assert "## Karar kriterleri" in rendered
    assert "## Türkçe morfoloji dayanıklılığı (strict recall)" in rendered
    assert "üçüncü taraf API" in rendered
    assert rendered.index("| core |") < rendered.index("| openai-llm |")


def test_render_comparison_tolerates_missing_slices(tmp_path: Path) -> None:
    legacy = result_fixture("legacy", 0.4)
    del legacy["slices"]
    report_path = write_results(tmp_path, [legacy])
    output = tmp_path / "out.md"
    render_comparison(report_path, output)
    assert "| legacy |" in output.read_text(encoding="utf-8")
