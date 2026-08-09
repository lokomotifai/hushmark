#!/usr/bin/env python3
"""Generate and lock hushmark-bench-v0."""

from __future__ import annotations

import argparse
from pathlib import Path

from hushmark_bench.dataset import load_dataset, write_dataset, write_lock

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--repetitions", type=int, default=8)
    args = parser.parse_args()
    data_path = ROOT / "data" / "hushmark-bench-v0.jsonl"
    lock_path = ROOT / "data" / "hushmark-bench-v0.sha256"
    digest = write_dataset(data_path, args.seed, args.repetitions)
    write_lock(lock_path, digest, data_path)
    examples = load_dataset(data_path)
    if len(examples) < 2_000:
        raise RuntimeError(f"benchmark has only {len(examples)} examples")
    print(f"wrote {len(examples)} examples sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
