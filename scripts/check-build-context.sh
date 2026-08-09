#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ignore_file="$repo_dir/deploy/docker/.dockerignore"
docker_ignore_file="$repo_dir/.dockerignore"
canary="HUSHMARK-CORPUS-"
canary+="CANARY-7f3a9d"

required=(research briefs hushmark PLAN.md PLAN-BRIEF.md EXECUTABLE-PLAN-PROMPT.md)
for path in "${required[@]}"; do
  if ! grep -Fxq "$path" "$ignore_file"; then
    echo "Missing build-context exclusion: $path" >&2
    exit 1
  fi
done

if [[ $(head -n 1 "$docker_ignore_file") != "**" ]]; then
  echo "Root Docker build context is not deny-by-default." >&2
  exit 1
fi
for path in research briefs hushmark PLAN.md PLAN-BRIEF.md EXECUTABLE-PLAN-PROMPT.md; do
  if grep -Fxq "!$path" "$docker_ignore_file"; then
    echo "Private path is allowlisted in root Docker context: $path" >&2
    exit 1
  fi
done

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

tar -C "$repo_dir" \
  --exclude-from="$ignore_file" \
  --exclude=.git \
  -cf "$tmp_dir/context.tar" .

if tar -tf "$tmp_dir/context.tar" | grep -E '(^|/)(research|briefs|hushmark)(/|$)|(^|/)PLAN(-BRIEF)?\.md$|EXECUTABLE-PLAN-PROMPT\.md'; then
  echo "Private corpus path leaked into the build context." >&2
  exit 1
fi

if grep -aFq "$canary" "$tmp_dir/context.tar"; then
  echo "Corpus canary leaked into the build context." >&2
  exit 1
fi

echo "Build context contains 0 private corpus paths and no canary."
