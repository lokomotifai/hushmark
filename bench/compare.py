#!/usr/bin/env python3
"""Render the cross-engine comparison report from stored engine results."""

from __future__ import annotations

import argparse
from pathlib import Path

from hushmark_bench.compare import render_comparison


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render_comparison(args.report, args.output)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
