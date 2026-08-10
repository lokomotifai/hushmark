from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gpu_bootstrap_dry_run_pins_cuda_torch_and_avoids_uv_run() -> None:
    result = subprocess.run(
        ["bash", "scripts/bootstrap-gpu.sh", "--dry-run"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "torch=2.13.0" in result.stdout
    assert "https://download.pytorch.org/whl/cu130" in result.stdout
    assert "--no-install-package torch" in result.stdout
    assert "uv run is intentionally not used" in result.stdout
