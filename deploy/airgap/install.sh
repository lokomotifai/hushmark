#!/usr/bin/env bash
set -euo pipefail

bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cluster_name=""
namespace=hushmark
evaluation=false
load_only=false

usage() {
  echo "usage: $0 [--load-only] [--kind-cluster NAME --evaluation] [--namespace NAME]" >&2
}

while (($# > 0)); do
  case "$1" in
    --load-only)
      load_only=true
      shift
      ;;
    --kind-cluster)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      cluster_name=$2
      shift 2
      ;;
    --namespace)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      namespace=$2
      shift 2
      ;;
    --evaluation)
      evaluation=true
      shift
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$bundle_dir" && sha256sum --check SHA256SUMS)
elif command -v shasum >/dev/null 2>&1; then
  (cd "$bundle_dir" && shasum -a 256 -c SHA256SUMS)
else
  echo "sha256sum or shasum is required" >&2
  exit 1
fi

images_archive="$bundle_dir/images/hushmark-images.tar"
if [[ "$load_only" == true ]]; then
  command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
  docker load --input "$images_archive"
fi

if [[ -z "$cluster_name" ]]; then
  [[ "$evaluation" == false ]] || { echo "--evaluation requires --kind-cluster" >&2; exit 2; }
  [[ "$load_only" == true ]] || { usage; exit 2; }
  echo "Verified and loaded Hushmark 0.1.1 images."
  exit 0
fi

for tool in kind kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || { echo "$tool is required" >&2; exit 1; }
done
kind get clusters | grep -Fxq "$cluster_name" || { echo "kind cluster not found: $cluster_name" >&2; exit 1; }
kind load image-archive --name "$cluster_name" "$images_archive"

if [[ "$evaluation" == false ]]; then
  echo "Verified and loaded Hushmark 0.1.1 images into kind cluster $cluster_name."
  exit 0
fi

kubectl create namespace "$namespace" --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace "$namespace" hushmark.ai/gateway-access=true --overwrite
kubectl -n "$namespace" create secret generic hushmark-gateway \
  --from-literal=api-keys=hm_k1_evaluation_local_key \
  --from-literal=openai-api-key=evaluation \
  --from-literal=anthropic-api-key=evaluation \
  --from-literal=core-service-token="$(openssl rand -hex 32)" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n "$namespace" apply -f "$bundle_dir/manifests/eval-services.yaml"

helm upgrade --install hushmark "$bundle_dir/chart/hushmark-0.1.1.tgz" \
  --namespace "$namespace" \
  --set fullnameOverride=hushmark \
  --set core.image.tag=0.1.1-model \
  --set core.image.pullPolicy=Never \
  --set core.nerBackend=onnx \
  --set gateway.image.pullPolicy=Never \
  --set gateway.openaiUpstream=http://fake-upstream:9000/v1 \
  --set gateway.anthropicUpstream=http://fake-upstream:9000/v1 \
  --set console.image.pullPolicy=Never \
  --set enterprise.enabled=false \
  --set postgres.enabled=false \
  --wait --timeout 8m

kubectl -n "$namespace" rollout status deployment/fake-upstream --timeout=120s
echo "Offline evaluation profile installed in kind cluster $cluster_name."
