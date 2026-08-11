#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

uv run python scripts/check-packaging.py
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml config --quiet

production_tmp=$(mktemp -d)
trap 'rm -rf "$production_tmp"' EXIT
mkdir -p "$production_tmp/models/hushmark-tr" "$production_tmp/secrets"
touch "$production_tmp/secrets/api-keys"
touch "$production_tmp/secrets/openai-api-key"
touch "$production_tmp/secrets/anthropic-api-key"
HUSHMARK_DOMAIN=localhost \
HUSHMARK_MODEL_DIR="$production_tmp/models" \
HUSHMARK_SECRETS_DIR="$production_tmp/secrets" \
  docker compose -f deploy/docker/compose.production.yaml config --quiet

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
