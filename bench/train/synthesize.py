#!/usr/bin/env python3
"""Create or deterministically verify the scaled hushmark-tr synthetic corpus."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from hushmark_bench.training import DEFAULT_SYNTHETIC_EXAMPLES, synthesize

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--examples", type=int, default=DEFAULT_SYNTHETIC_EXAMPLES)
    parser.add_argument("--output", type=Path, default=ROOT / "bench/train/outputs/synthetic.jsonl")
    parser.add_argument(
        "--profile",
        choices=("full", "legacy"),
        default="full",
        help="full excludes every locked v0 benchmark row; legacy reproduces earlier evidence",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    exclude_locked = args.profile == "full"

    if args.check:
        first = synthesize(seed=args.seed, count=args.examples, exclude_locked=exclude_locked)
        second = synthesize(seed=args.seed, count=args.examples, exclude_locked=exclude_locked)
        if first != second:
            raise RuntimeError("scaled synthesis is not deterministic")
        print(json.dumps({"deterministic": True, **asdict(first)}, sort_keys=True))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary = synthesize(
        seed=args.seed,
        count=args.examples,
        output_path=args.output,
        exclude_locked=exclude_locked,
    )
    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {"seed": args.seed, "profile": args.profile, **asdict(summary)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {summary.examples} examples sha256={summary.sha256} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
