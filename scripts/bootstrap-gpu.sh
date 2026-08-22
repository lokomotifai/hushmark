#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
torch_version=2.13.0
torch_index_url=https://download.pytorch.org/whl/cu130
torch_wheel_url=https://download-r2.pytorch.org/whl/cu130/torch-2.13.0%2Bcu130-cp312-cp312-manylinux_2_28_x86_64.whl
torch_wheel_sha256=8db7338e6895c3d4bd89a02ff4209507d1f0cf2ffeb3b898538b5a07d1ea8c1e
uv_cache_dir=${HUSHMARK_UV_CACHE_DIR:-/workspace/.cache/hushmark-uv}
fetch_models=${HUSHMARK_FETCH_MODELS:-1}

print_plan() {
  echo "repository=$repo_dir"
  echo "python=3.12"
  echo "torch=$torch_version"
  echo "torch_index=$torch_index_url"
  echo "torch_wheel=$torch_wheel_url"
  echo "torch_wheel_sha256=$torch_wheel_sha256"
  echo "uv_cache=$uv_cache_dir"
  echo "fetch_models=$fetch_models"
  echo "sync=uv sync --frozen --all-packages --no-install-package torch"
  echo "install=uv pip install --python .venv/bin/python --reinstall <pinned-wheel>#sha256=<pinned-hash>"
  echo "execution=.venv/bin/python (uv run is intentionally not used after the CUDA override)"
}

verify_platform() {
  .venv/bin/python - <<'PY'
import platform
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"GPU wheel requires Python 3.12, got {platform.python_version()}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(
        f"GPU wheel requires Linux x86_64, got {platform.system()} {platform.machine()}"
    )
PY
}

verify_cuda() {
  HUSHMARK_EXPECTED_TORCH="$torch_version" .venv/bin/python - <<'PY'
import json
import os

import torch

expected = os.environ["HUSHMARK_EXPECTED_TORCH"]
if torch.__version__.split("+")[0] != expected:
    raise SystemExit(f"unexpected torch version: {torch.__version__} (expected {expected})")
if not torch.cuda.is_available():
    raise SystemExit("CUDA verification failed: torch.cuda.is_available() is false")
if torch.version.cuda is None:
    raise SystemExit("CUDA verification failed: torch is a CPU-only build")
print(
    json.dumps(
        {
            "torch": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "gpu_count": torch.cuda.device_count(),
            "gpu_name": torch.cuda.get_device_name(0),
            "gpu_capability": list(torch.cuda.get_device_capability(0)),
            "bf16_supported": torch.cuda.is_bf16_supported(),
        },
        sort_keys=True,
    )
)
PY
}

case "${1:-}" in
  --dry-run)
    print_plan
    exit 0
    ;;
  --check)
    cd "$repo_dir"
    verify_cuda
    exit 0
    ;;
  "")
    ;;
  *)
    echo "usage: $0 [--dry-run|--check]" >&2
    exit 2
    ;;
esac

command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
}
command -v nvidia-smi >/dev/null 2>&1 || {
  echo "nvidia-smi is required; run this script inside a CUDA-enabled Pod" >&2
  exit 1
}

cd "$repo_dir"
mkdir -p "$uv_cache_dir"
export UV_CACHE_DIR="$uv_cache_dir"
print_plan
nvidia-smi
uv sync --frozen --all-packages --no-install-package torch
verify_platform
uv pip install \
  --python .venv/bin/python \
  --reinstall \
  "${torch_wheel_url}#sha256=${torch_wheel_sha256}" \
  --index-url "$torch_index_url"
verify_cuda

if [[ "$fetch_models" == "1" ]]; then
  .venv/bin/python scripts/fetch-models.py
fi

echo "GPU bootstrap complete. Use .venv/bin/python for all training commands."
