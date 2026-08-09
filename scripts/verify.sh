#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

pnpm_cmd="$repo_dir/node_modules/.bin/pnpm"
if [[ ! -x "$pnpm_cmd" ]]; then
  echo "Local pnpm is missing; run ./scripts/bootstrap.sh first." >&2
  exit 1
fi

"$pnpm_cmd" format:check
"$pnpm_cmd" lint
"$pnpm_cmd" typecheck
"$pnpm_cmd" test
"$pnpm_cmd" build
"$pnpm_cmd" depcruise
"$pnpm_cmd" depcruise:fixture

uv run ruff format --check bench core tools scripts/fetch-models.py
uv run ruff check bench core tools scripts/fetch-models.py
uv run mypy bench/src core/src
uv run pytest
uv run lint-imports
uv run python tools/codegen/generate.py --check
uv run python tools/codegen/claims_lint.py

./scripts/check-build-context.sh

if rg -n --hidden --glob '!research/**' --glob '!briefs/**' --glob '!hushmark/**' \
  --glob '!.git/**' \
  --glob '!node_modules/**' --glob '!.venv/**' --glob '!dist/**' --glob '!.turbo/**' \
  --glob '!coverage/**' --glob '!.pytest_cache/**' --glob '!.ruff_cache/**' \
  --glob '!.mypy_cache/**' --glob '!.import_linter_cache/**' \
  --glob '!PLAN.md' --glob '!PLAN-BRIEF.md' --glob '!EXECUTABLE-PLAN-PROMPT.md' \
  '([T]ODO|[T]BD|\.skip\(|pytest\.mark\.skip)' .; then
  echo "Placeholder or skipped-test marker found." >&2
  exit 1
fi

echo "All verification gates passed."
