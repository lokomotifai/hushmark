#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

run_dir=$(mktemp -d)
processes=()
cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then
    for log in core upstream gateway; do
      echo "===== ${log}.log =====" >&2
      sed -n '1,240p' "$run_dir/${log}.log" >&2 || true
    done
  fi
  for process in "${processes[@]}"; do kill "$process" 2>/dev/null || true; done
  rm -rf "$run_dir"
  return "$status"
}
trap cleanup EXIT

HUSHMARK_CORE_ALLOW_UNAUTHENTICATED=true \
HUSHMARK_CORE_NER_BACKEND=disabled HUSHMARK_CORE_PORT=8000 \
  uv run --frozen --package hushmark-core hushmark-core >"$run_dir/core.log" 2>&1 &
processes+=("$!")
PORT=9000 node deploy/docker/eval/fake-upstream.mjs >"$run_dir/upstream.log" 2>&1 &
processes+=("$!")
HUSHMARK_GATEWAY_HOST=127.0.0.1 \
HUSHMARK_GATEWAY_PORT=8080 \
HUSHMARK_API_KEYS=hm_k1_evaluation_local_key \
HUSHMARK_CORE_URL=http://127.0.0.1:8000 \
HUSHMARK_OPENAI_UPSTREAM=http://127.0.0.1:9000/v1 \
HUSHMARK_ANTHROPIC_UPSTREAM=http://127.0.0.1:9000/v1 \
HUSHMARK_POLICY_PATH=packages/gateway/policy.yaml \
  env -u HUSHMARK_PERF_LIMIT_MULTIPLIER \
  node packages/gateway/dist/cli.js >"$run_dir/gateway.log" 2>&1 &
processes+=("$!")

for port in 8000 8080 9000; do
  ready=false
  for _ in {1..60}; do
    if curl --fail --silent "http://127.0.0.1:${port}/healthz" >/dev/null; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ $ready != true ]]; then
    echo "Service on port ${port} did not become ready within 60 seconds." >&2
    exit 1
  fi
done

HUSHMARK_PERF_PROFILE=${HUSHMARK_PERF_PROFILE:-"CI local stack, L0-only regression tripwire"} \
  ./scripts/perf-report.sh
