#!/bin/sh
set -eu

for forbidden in \
  briefs \
  research \
  hushmark \
  dataset-prep \
  EXECUTABLE-PLAN-PROMPT.md \
  PLAN-BRIEF.md \
  PLAN.md \
  security-review.md \
  roast.md
do
  if [ -n "$(git ls-files -- "$forbidden" "$forbidden/**")" ]; then
    echo "forbidden private path is tracked: $forbidden" >&2
    exit 1
  fi
done

limit_bytes=20971520
git ls-files | while IFS= read -r path
do
  size=$(git cat-file -s ":$path")
  if [ "$size" -gt "$limit_bytes" ]; then
    echo "tracked file exceeds 20 MiB safety limit: $path ($size bytes)" >&2
    exit 1
  fi
done
