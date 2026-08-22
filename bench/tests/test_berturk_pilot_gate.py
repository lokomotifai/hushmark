from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_berturk_pilot", ROOT / "bench/train/check_berturk_pilot.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_manifest() -> dict[str, Any]:
    return {
        "architecture": "berturk-fixed-span-ner",
        "run_kind": "pilot",
        "complete": False,
        "adoption_eligible": False,
        "max_steps": 1000,
        "optimizer_steps": 1000,
        "stop_reason": "max-steps",
        "mean_loss": 0.5,
        "final_loss": 0.4,
        "development_macro_f1": 0.7,
        "pilot_quality_pass": True,
        "amp": "bf16",
        "hardware": {
            "gpu_name": "NVIDIA A100-SXM4-80GB",
            "peak_allocated_bytes": 20 * 1024**3,
        },
    }


def test_berturk_pilot_gate_accepts_bounded_a100_run() -> None:
    assert MODULE.pilot_verdict(valid_manifest()) == {"pass": True, "reasons": []}


def test_berturk_pilot_gate_rejects_low_quality_run() -> None:
    manifest = valid_manifest()
    manifest["pilot_quality_pass"] = False
    verdict = MODULE.pilot_verdict(manifest)
    assert verdict["pass"] is False
    assert "development macro-F1 floor" in " ".join(verdict["reasons"])
