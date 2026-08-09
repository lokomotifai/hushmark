#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

uv run python scripts/check-packaging.py
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml config --quiet

helm_cmd=${HELM_BIN:-helm}
if ! command -v "$helm_cmd" >/dev/null 2>&1 && [[ ! -x "$helm_cmd" ]]; then
  echo "Helm is required for chart validation; set HELM_BIN to an executable." >&2
  exit 1
fi
"$helm_cmd" lint deploy/helm/hushmark --strict
"$helm_cmd" template hushmark deploy/helm/hushmark >/dev/null
"$helm_cmd" template hushmark deploy/helm/hushmark \
  --set enterprise.enabled=true \
  --set postgres.enabled=true \
  --set postgres.persistence.enabled=false >/dev/null

echo "Compose and Helm render gates passed."
