#!/usr/bin/env python3
"""Apply the non-negotiable gate between the A100 pilot and full training."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def pilot_verdict(manifest: Mapping[str, Any]) -> dict[str, Any]:
    hardware = manifest.get("hardware")
    hardware = hardware if isinstance(hardware, Mapping) else {}
    reasons: list[str] = []
    if manifest.get("run_kind") != "pilot" or manifest.get("complete") is not False:
        reasons.append("run is not an incomplete bounded pilot")
    if manifest.get("adoption_eligible") is not False:
        reasons.append("pilot must be adoption-ineligible")
    if manifest.get("max_steps") != 500 or manifest.get("optimizer_steps") != 500:
        reasons.append("pilot did not complete exactly 500 optimizer steps")
    if manifest.get("stop_reason") != "max-steps":
        reasons.append("pilot did not stop at its max-step boundary")
    for field in ("mean_loss", "final_loss"):
        value = manifest.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            reasons.append(f"pilot {field} is missing or non-finite")
    if "A100" not in str(hardware.get("gpu_name", "")):
        reasons.append("pilot did not run on an A100")
    peak = hardware.get("peak_allocated_bytes")
    if not isinstance(peak, int) or peak <= 0 or peak >= 78 * 1024**3:
        reasons.append("pilot peak GPU allocation is missing or exceeds the 80 GB safety limit")
    if manifest.get("amp") not in {"bf16", "fp16"}:
        reasons.append("pilot did not use CUDA mixed precision")
    if manifest.get("development_gate_pass") is not True:
        reasons.append("pilot did not pass the combined legacy/new development gate")
    return {"pass": not reasons, "reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("pilot manifest must be an object")
    verdict = pilot_verdict(manifest)
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
