#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

k6_cmd=${K6_BIN:-k6}
if ! command -v "$k6_cmd" >/dev/null 2>&1 && [[ ! -x "$k6_cmd" ]]; then
  echo "k6 is required; set K6_BIN to an executable." >&2
  exit 1
fi

report_date=${HUSHMARK_PERF_DATE:-$(date -u +%Y-%m-%d)}
profile=${HUSHMARK_PERF_PROFILE:-"4 vCPU core quota, 6 GiB core memory, ONNX int8"}
limit_multiplier=${HUSHMARK_PERF_LIMIT_MULTIPLIER:-1}
raw_dir=$(mktemp -d)
trap 'rm -rf "$raw_dir"' EXIT

"$k6_cmd" run --summary-export "$raw_dir/core.json" perf/k6/core-analyze.js
"$k6_cmd" run --summary-export "$raw_dir/gateway.json" perf/k6/gateway-roundtrip.js
"$k6_cmd" run --summary-export "$raw_dir/stream.json" perf/k6/gateway-stream.js
uv run python scripts/perf-report.py \
  --core "$raw_dir/core.json" \
  --gateway "$raw_dir/gateway.json" \
  --stream "$raw_dir/stream.json" \
  --profile "$profile" \
  --limit-multiplier "$limit_multiplier" \
  --output "perf/reports/$report_date.md"

echo "Wrote perf/reports/$report_date.md"
