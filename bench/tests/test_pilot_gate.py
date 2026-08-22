from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_pilot", ROOT / "bench/train/check_pilot.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def passing_manifest() -> dict[str, Any]:
    return {
        "run_kind": "pilot",
        "complete": False,
        "adoption_eligible": False,
        "max_steps": 500,
        "optimizer_steps": 500,
        "stop_reason": "max-steps",
        "mean_loss": 0.3,
        "final_loss": 0.2,
        "amp": "bf16",
        "development_gate_pass": True,
        "hardware": {
            "gpu_name": "NVIDIA A100-SXM4-80GB",
            "peak_allocated_bytes": 20 * 1024**3,
        },
    }


def test_pilot_gate_passes_complete_a100_pilot() -> None:
    assert MODULE.pilot_verdict(passing_manifest()) == {"pass": True, "reasons": []}


def test_pilot_gate_rejects_failed_development_or_memory_boundary() -> None:
    manifest = passing_manifest()
    manifest["development_gate_pass"] = False
    manifest["hardware"]["peak_allocated_bytes"] = 79 * 1024**3
    verdict = MODULE.pilot_verdict(manifest)
    assert verdict["pass"] is False
    assert len(verdict["reasons"]) == 2
