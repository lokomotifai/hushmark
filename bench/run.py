#!/usr/bin/env python3
"""Run one benchmark engine and update the combined baseline report."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal, cast

from hushmark_bench.runner import run_benchmark

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine",
        choices=("core", "presidio-default", "presidio-tr", "gliner-raw", "openai-llm"),
        required=True,
    )
    parser.add_argument("--backend", choices=("disabled", "torch", "onnx"), default="onnx")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    backend = cast(Literal["disabled", "torch", "onnx"], args.backend)
    result = run_benchmark(
        engine=args.engine,
        backend=backend,
        data_path=ROOT / "data" / "hushmark-bench-v0.jsonl",
        lock_path=ROOT / "data" / "hushmark-bench-v0.sha256",
        report_path=args.report,
        limit=args.limit,
    )
    strict = result["strict"]["micro"]
    print(
        f"{result['engine']} strict P={strict['precision']:.3f} "
        f"R={strict['recall']:.3f} F1={strict['f1']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
