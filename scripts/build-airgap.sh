#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

version=0.1.0
bundle_name="hushmark-airgap-$version"
artifact="$repo_dir/dist/$bundle_name.tar"
stage_parent=$(mktemp -d)
stage="$stage_parent/$bundle_name"
cleanup() { rm -rf "$stage_parent"; }
trap cleanup EXIT

for tool in docker helm tar; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
  echo "sha256sum or shasum is required" >&2
  exit 1
fi

./scripts/check-build-context.sh
uv run python tools/export-onnx.py --verify-only

docker build --target slim -f deploy/docker/core.Dockerfile -t "hushmark/core:$version" .
docker build \
  --build-arg "BASE_IMAGE=hushmark/core:$version" \
  -f deploy/docker/core-airgap.Dockerfile \
  -t "hushmark/core:$version-model" \
  models/gliner_multi_pii-v1
docker build -f deploy/docker/gateway.Dockerfile -t "hushmark/gateway:$version" .
docker build -f deploy/docker/console.Dockerfile -t "hushmark/console:$version" .
./scripts/check-image-canary.sh \
  "hushmark/core:$version-model" \
  "hushmark/gateway:$version" \
  "hushmark/console:$version"

mkdir -p "$stage/images" "$stage/chart" "$stage/models/gliner_multi_pii-v1" "$stage/manifests"
docker save --output "$stage/images/hushmark-images.tar" \
  "hushmark/core:$version-model" \
  "hushmark/gateway:$version" \
  "hushmark/console:$version"
helm package deploy/helm/hushmark --destination "$stage/chart" >/dev/null

for model_file in gliner_config.json gliner_config.source.json model_quantized.onnx tokenizer.json tokenizer_config.json; do
  source_file="$repo_dir/models/gliner_multi_pii-v1/$model_file"
  [[ -f "$source_file" ]] || { echo "verified model file is missing: $source_file" >&2; exit 1; }
  cp "$source_file" "$stage/models/gliner_multi_pii-v1/$model_file"
done
cp deploy/airgap/install.sh "$stage/install.sh"
cp deploy/airgap/eval-services.yaml "$stage/manifests/eval-services.yaml"
cp docs/install-airgap.md "$stage/README.md"
chmod 755 "$stage/install.sh"

(
  cd "$stage"
  while IFS= read -r path; do
    if command -v sha256sum >/dev/null 2>&1; then
      sha256sum "$path"
    else
      shasum -a 256 "$path"
    fi
  done < <(find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort)
) >"$stage/SHA256SUMS"

mkdir -p "$repo_dir/dist"
tar -cf "$artifact.tmp" -C "$stage_parent" "$bundle_name"
mv "$artifact.tmp" "$artifact"

if tar -tf "$artifact" | grep -E '(^|/)(research|briefs)(/|$)|PLAN(-BRIEF)?\.md|EXECUTABLE-PLAN-PROMPT\.md'; then
  echo "Private corpus path found in air-gap bundle" >&2
  exit 1
fi
canary='HUSHMARK-CORPUS-'
canary+='CANARY-7f3a9d'
if rg -a --fixed-strings --quiet "$canary" "$artifact"; then
  echo "Corpus canary found in air-gap bundle" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$artifact"
else
  shasum -a 256 "$artifact"
fi
echo "Air-gap bundle created: $artifact"
