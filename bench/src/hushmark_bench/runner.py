"""Benchmark orchestration and L0 evidence gate."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Literal, Protocol

from hushmark_bench.dataset import deterministic_types, load_dataset
from hushmark_bench.metrics import evaluate
from hushmark_bench.report import render_report, write_result
from hushmark_bench.slices import build_slices


class Adapter(Protocol):
    name: str
    model_id: str
    model_sha256: str | None
    runtime: str

    def predict(self, text: str) -> list[dict[str, object]]: ...


def verify_lock(data_path: Path, lock_path: Path) -> str:
    expected, filename = lock_path.read_text(encoding="utf-8").strip().split(maxsplit=1)
    if filename != f"bench/data/{data_path.name}":
        raise ValueError("benchmark lock filename mismatch")
    actual = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError("benchmark dataset SHA-256 mismatch")
    return actual


def build_adapter(engine: str, backend: Literal["disabled", "torch", "onnx"]) -> Adapter:
    if engine == "core":
        from hushmark_bench.adapters.core_adapter import CoreAdapter

        return CoreAdapter(backend)
    if engine == "presidio-default":
        from hushmark_bench.adapters.presidio_default import PresidioDefaultAdapter

        return PresidioDefaultAdapter()
    if engine == "presidio-tr":
        from hushmark_bench.adapters.presidio_tr import PresidioTurkishAdapter

        return PresidioTurkishAdapter()
    if engine == "gliner-raw":
        from hushmark_bench.adapters.gliner_raw import GlinerRawAdapter

        return GlinerRawAdapter()
    if engine == "openai-llm":
        from hushmark_bench.adapters.openai_llm import OpenAiLlmAdapter

        return OpenAiLlmAdapter()
    raise ValueError(f"unsupported engine: {engine}")


def enforce_l0_gate(strict: dict[str, Any]) -> None:
    for entity_type in sorted(deterministic_types()):
        metrics = strict["per_type"].get(entity_type)
        if not metrics or not metrics["support"]:
            raise RuntimeError(f"L0 benchmark has no gold support for {entity_type}")
        if metrics["precision"] < 1.0 or metrics["recall"] < 0.99:
            raise RuntimeError(
                f"L0 gate failed for {entity_type}: "
                f"P={metrics['precision']:.3f} R={metrics['recall']:.3f}"
            )


def run_benchmark(
    *,
    engine: str,
    backend: Literal["disabled", "torch", "onnx"],
    data_path: Path,
    lock_path: Path,
    report_path: Path,
    limit: int | None = None,
) -> dict[str, Any]:
    digest = verify_lock(data_path, lock_path)
    examples = load_dataset(data_path)
    if limit is not None:
        examples = examples[:limit]
    adapter = build_adapter(engine, backend)
    predictions: list[list[dict[str, object]]] = []
    durations: list[float] = []
    started = time.perf_counter()
    for index, example in enumerate(examples, start=1):
        call_started = time.perf_counter()
        predictions.append(adapter.predict(example["text"]))
        durations.append(time.perf_counter() - call_started)
        if index % 100 == 0:
            print(f"evaluated {index}/{len(examples)}", flush=True)
    duration = time.perf_counter() - started
    gold = [example["entities"] for example in examples]
    strict = evaluate(gold, predictions, mode="strict")
    partial = evaluate(gold, predictions, mode="partial")
    if engine == "core" and limit is None:
        enforce_l0_gate(strict)
    result: dict[str, Any] = {
        "schema_version": 1,
        "engine": adapter.name,
        "backend": adapter.runtime,
        "model_id": adapter.model_id,
        "model_sha256": adapter.model_sha256,
        "dataset": {
            "name": data_path.name,
            "examples": len(examples),
            "sha256": digest,
        },
        "duration_seconds": duration,
        "strict": strict,
        "partial": partial,
        "slices": build_slices(examples, gold, predictions, strict, partial, durations),
    }
    write_result(report_path, result)
    render_report(report_path)
    return result
