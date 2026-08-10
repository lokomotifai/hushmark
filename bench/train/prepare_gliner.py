#!/usr/bin/env python3
"""Convert benchmark or exported Turkish AI4Privacy JSONL to GLiNER format."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal, cast

from hushmark_bench.training import load_model_labels, prepare_jsonl

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-format",
        choices=("hushmark", "synthetic-full", "ai4privacy"),
        required=True,
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    args = parser.parse_args()

    count, digest = prepare_jsonl(
        input_path=args.input,
        output_path=args.output,
        source_format=cast(Literal["hushmark", "synthetic-full", "ai4privacy"], args.source_format),
        labels=load_model_labels(args.registry),
        limit=args.limit,
    )
    print(f"prepared {count} GLiNER records sha256={digest} at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
