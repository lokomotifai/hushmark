#!/usr/bin/env python3
"""Create the deterministic development corpus reserved outside full training."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from hushmark_bench.training import DEVELOPMENT_EXAMPLES, development_examples

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "bench/train/outputs/synthetic-dev.jsonl",
    )
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    domains: Counter[str] = Counter()
    morphologies: Counter[str] = Counter()
    with args.output.open("w", encoding="utf-8") as output:
        for example in development_examples(args.seed):
            line = json.dumps(asdict(example), ensure_ascii=False, separators=(",", ":")) + "\n"
            output.write(line)
            digest.update(line.encode())
            domains[example.domain] += 1
            morphologies[example.morphology[0]] += 1

    metadata = {
        "schema_version": 1,
        "profile": "development",
        "seed": args.seed,
        "examples": DEVELOPMENT_EXAMPLES,
        "sha256": digest.hexdigest(),
        "domains": dict(sorted(domains.items())),
        "morphologies": dict(sorted(morphologies.items())),
    }
    args.output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {DEVELOPMENT_EXAMPLES} development examples "
        f"sha256={metadata['sha256']} to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
