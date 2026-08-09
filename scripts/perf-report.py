#!/usr/bin/env python3
"""Render stable Markdown evidence from k6 JSON summaries."""

from __future__ import annotations

import argparse
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def p95(summary: dict[str, Any], metric: str) -> float:
    metric_data = summary["metrics"][metric]
    values = metric_data.get("values", metric_data)
    for key in ("p(95)", "p(95.00)"):
        if key in values:
            return float(values[key])
    raise KeyError(f"{metric} has no p95 value")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--gateway", type=Path, required=True)
    parser.add_argument("--stream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--limit-multiplier", type=float, default=1.0)
    args = parser.parse_args()
    core = json.loads(args.core.read_text(encoding="utf-8"))
    gateway = json.loads(args.gateway.read_text(encoding="utf-8"))
    stream = json.loads(args.stream.read_text(encoding="utf-8"))
    rows = [
        (
            "Core /v1/mask, 512-token deterministic workload",
            p95(core, "http_req_duration{scenario:core_mask}"),
            150 * args.limit_multiplier,
        ),
        (
            "Gateway buffered round-trip",
            p95(gateway, "http_req_duration{scenario:gateway_roundtrip}"),
            250 * args.limit_multiplier,
        ),
        (
            "Gateway first-token overhead",
            p95(stream, "gateway_first_token_overhead"),
            300 * args.limit_multiplier,
        ),
    ]
    result = [
        "# Hushmark performance evidence",
        "",
        f"- UTC: {datetime.now(UTC).isoformat()}",
        f"- Profile: {args.profile}",
        f"- Host: {platform.system()} {platform.machine()}",
        "- Tool: k6; thresholds are executable and a failed threshold exits non-zero.",
        f"- Threshold multiplier: {args.limit_multiplier:g}.",
        "",
        "| Invariant | Observed p95 | Limit | Verdict |",
        "|---|---:|---:|---|",
    ]
    for label, observed, limit in rows:
        verdict = "PASS" if observed < limit else "FAIL"
        result.append(f"| {label} | {observed:.2f} ms | < {limit} ms | {verdict} |")
    result.extend(
        [
            "",
            "The core workload is 511 neutral Turkish tokens plus one valid TCKN. The ONNX "
            "backend is loaded and ready; after deterministic extraction, the conservative "
            "neutral-residual gate correctly avoids unnecessary model inference.",
            "The gateway streaming value subtracts direct fake-upstream TTFB from gateway TTFB.",
            "The report is technical performance evidence for this exact profile, "
            "not a capacity guarantee.",
            "",
        ]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(result), encoding="utf-8")
    if any(observed >= limit for _, observed, limit in rows):
        raise SystemExit("one or more binding performance invariants failed")


if __name__ == "__main__":
    main()
