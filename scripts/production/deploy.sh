#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file=$repo_dir/deploy/docker/compose.production.yaml
env_file=${1:-/etc/hushmark/production.env}

"$repo_dir/scripts/production/preflight.sh" "$env_file"

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

compose=(docker compose --env-file "$env_file" -f "$compose_file")

"${compose[@]}" pull
"${compose[@]}" up -d --remove-orphans --wait --wait-timeout 300

"${compose[@]}" exec -T core python -c \
  'import json, pathlib, urllib.request; token=pathlib.Path("/run/secrets/core_service_token").read_text().strip(); payload=json.dumps({"items":[{"id":"smoke","text":"TCKN 10000000146"}],"language":"tr","include_values":False}).encode(); request=urllib.request.Request("http://127.0.0.1:8000/v1/mask", data=payload, headers={"content-type":"application/json","authorization":f"Bearer {token}"}); result=json.loads(urllib.request.urlopen(request, timeout=30).read()); assert "[TCKN_1]" in result["items"][0]["masked_text"]'

curl_args=(--fail --silent --show-error --retry 12 --retry-all-errors --retry-delay 5)
if [[ $HUSHMARK_DOMAIN == localhost ]]; then
  curl_args+=(--insecure)
fi
curl "${curl_args[@]}" "https://$HUSHMARK_DOMAIN:${HUSHMARK_HTTPS_PORT:-443}/readyz" >/dev/null

echo "Hushmark production deployment is ready at https://$HUSHMARK_DOMAIN."
