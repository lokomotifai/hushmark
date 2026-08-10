#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  echo "usage: $0 <image> [image ...]" >&2
  exit 2
fi

canary="HUSHMARK-CORPUS-"
canary+="CANARY-7f3a9d"

contains_canary() {
  local root=$1
  if command -v rg >/dev/null 2>&1; then
    rg -a --fixed-strings --quiet -- "$canary" "$root"
  else
    LC_ALL=C grep -R -a -F -q -- "$canary" "$root"
  fi
}

for image in "$@"; do
  scan_dir=$(mktemp -d)
  archive="$scan_dir/image.tar"
  docker save --output "$archive" "$image"
  tar -xf "$archive" -C "$scan_dir"
  if contains_canary "$scan_dir"; then
    echo "Corpus canary found in image layers: $image" >&2
    rm -rf "$scan_dir"
    exit 1
  fi
  if tar -tf "$archive" | grep -E '(^|/)(research|briefs|hushmark)(/|$)|PLAN(-BRIEF)?\.md|EXECUTABLE-PLAN-PROMPT\.md'; then
    echo "Private corpus path found in image archive: $image" >&2
    rm -rf "$scan_dir"
    exit 1
  fi
  rm -rf "$scan_dir"
  echo "Image contains no private corpus path or canary: $image"
done
