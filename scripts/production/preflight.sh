#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file=${HUSHMARK_COMPOSE_FILE:-$repo_dir/deploy/docker/compose.production.yaml}
env_file=${1:-/etc/hushmark/production.env}

fail() {
  echo "production preflight failed: $*" >&2
  exit 1
}

file_mode() {
  if stat -c '%a' "$1" >/dev/null 2>&1; then
    stat -c '%a' "$1"
  else
    stat -f '%Lp' "$1"
  fi
}

[[ -f "$env_file" && ! -L "$env_file" ]] || fail "environment file is missing or is a symlink: $env_file"
env_mode=$(file_mode "$env_file")
[[ $env_mode == 400 || $env_mode == 600 ]] || fail "environment file mode must be 0400 or 0600"

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

for variable_name in HUSHMARK_DOMAIN HUSHMARK_MODEL_DIR HUSHMARK_SECRETS_DIR; do
  [[ -n ${!variable_name:-} ]] || fail "$variable_name is required"
done

if [[ $HUSHMARK_DOMAIN != localhost ]]; then
  [[ $HUSHMARK_DOMAIN =~ ^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$ ]] ||
    fail "HUSHMARK_DOMAIN must be localhost or a fully qualified hostname"
fi
if [[ $HUSHMARK_DOMAIN == *.example.com && ${HUSHMARK_ALLOW_EXAMPLE_DOMAIN:-0} != 1 ]]; then
  fail "replace the example domain before deployment"
fi
[[ $HUSHMARK_MODEL_DIR == /* ]] || fail "HUSHMARK_MODEL_DIR must be an absolute path"
[[ $HUSHMARK_SECRETS_DIR == /* ]] || fail "HUSHMARK_SECRETS_DIR must be an absolute path"

for port_variable in HUSHMARK_HTTP_PORT HUSHMARK_HTTPS_PORT; do
  port=${!port_variable:-}
  if [[ -n $port ]]; then
    [[ $port =~ ^[1-9][0-9]*$ ]] || fail "$port_variable must be a positive integer without leading zeros"
    ((port >= 1 && port <= 65535)) || fail "$port_variable must be between 1 and 65535"
  fi
done

command -v docker >/dev/null 2>&1 || fail "docker is required"
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
docker info >/dev/null 2>&1 || fail "the Docker daemon is not reachable"

case $(uname -m) in
  x86_64 | amd64 | aarch64 | arm64) ;;
  *) fail "unsupported host architecture: $(uname -m)" ;;
esac

model_dir=$HUSHMARK_MODEL_DIR/hushmark-tr
model_files=(
  gliner_config.json
  model.onnx
  tokenizer.json
  tokenizer_config.json
)
expected_hashes=(
  61a066493aa5b64280be2af4686337553e9f7119f5c77f52e301e8b0ce5c2577
  c5e72ca974f2e671325314f5a2d1d7eb2e1951ccd3d5250b0e223787f22c35ed
  c5b8041501fcdee792b9b112dd592861f04391a24633a73fd9f05aaaf6e8eff1
  956b6974aa26891eba87a28b3f92fa7228804ad6b7a7e2a7ff0473dfb424d886
)

hash_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

for index in "${!model_files[@]}"; do
  filename=${model_files[$index]}
  path=$model_dir/$filename
  [[ -f "$path" ]] || fail "model file missing: $path"
  actual_hash=$(hash_file "$path")
  [[ $actual_hash == "${expected_hashes[$index]}" ]] || fail "model checksum mismatch: $filename"
done

for secret_name in api-keys openai-api-key anthropic-api-key core-service-token; do
  secret_path=$HUSHMARK_SECRETS_DIR/$secret_name
  [[ -f "$secret_path" && ! -L "$secret_path" ]] || fail "secret file is missing or is a symlink: $secret_path"
  secret_mode=$(file_mode "$secret_path")
  [[ $secret_mode == 400 || $secret_mode == 600 ]] || fail "secret file mode must be 0400 or 0600: $secret_name"
done

core_service_token=$(tr -d '\r\n' <"$HUSHMARK_SECRETS_DIR/core-service-token")
[[ ${#core_service_token} -ge 32 ]] || fail "core-service-token must contain at least 32 characters"

api_keys=$(tr -d '\r\n' <"$HUSHMARK_SECRETS_DIR/api-keys")
[[ -n $api_keys ]] || fail "api-keys is empty"
IFS=',' read -r -a parsed_api_keys <<<"$api_keys"
for api_key in "${parsed_api_keys[@]}"; do
  [[ $api_key =~ ^hm_k1_[A-Za-z0-9_-]{16,}$ ]] || fail "api-keys contains an invalid key"
done

docker compose --env-file "$env_file" -f "$compose_file" config --quiet

echo "Production preflight passed for $HUSHMARK_DOMAIN on $(uname -m)."
