#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

command -v pnpm >/dev/null 2>&1 || {
  echo "pnpm is required" >&2
  exit 1
}

command -v uv >/dev/null 2>&1 || {
  echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
}

pnpm_args=(install --frozen-lockfile)
if [[ -n "${HUSHMARK_PNPM_STORE_DIR:-}" ]]; then
  pnpm_args+=(--store-dir "$HUSHMARK_PNPM_STORE_DIR")
fi

pnpm "${pnpm_args[@]}"
uv sync --frozen --all-packages

if [[ "${HUSHMARK_FETCH_MODELS:-1}" == "1" ]]; then
  uv run python scripts/fetch-models.py
  if ! HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run python tools/export-onnx.py --verify-only; then
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run python tools/export-onnx.py
  fi
fi

echo "Bootstrap complete."
