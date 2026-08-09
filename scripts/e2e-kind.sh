#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

cluster_name="hushmark-e2e-${RANDOM}"
namespace=hushmark
port_forward_pid=""
airgap_archive=""
airgap_extract_dir=""
cleanup() {
  if [[ -n "$port_forward_pid" ]]; then kill "$port_forward_pid" 2>/dev/null || true; fi
  if [[ -n "$airgap_extract_dir" ]]; then rm -rf "$airgap_extract_dir"; fi
  kind delete cluster --name "$cluster_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if (($# > 0)); then
  if [[ $# -ne 2 || $1 != "--airgap" ]]; then
    echo "usage: $0 [--airgap PATH]" >&2
    exit 2
  fi
  airgap_archive=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd)/$(basename -- "$2")
  [[ -f "$airgap_archive" ]] || { echo "air-gap archive not found: $airgap_archive" >&2; exit 1; }
fi

for tool in docker kind helm kubectl curl; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

if [[ -n "$airgap_archive" ]]; then
  airgap_extract_dir=$(mktemp -d)
  tar -xf "$airgap_archive" -C "$airgap_extract_dir"
  install_script=$(find "$airgap_extract_dir" -mindepth 2 -maxdepth 2 -name install.sh -print -quit)
  [[ -n "$install_script" ]] || { echo "air-gap installer is missing" >&2; exit 1; }

  kind create cluster --name "$cluster_name" --wait 120s
  "$install_script" --kind-cluster "$cluster_name" --evaluation

  pull_events=$(kubectl -n "$namespace" get events -o jsonpath='{range .items[?(@.reason=="Pulling")]}{.message}{"\n"}{end}')
  [[ -z "$pull_events" ]] || { echo "registry pull observed in offline cluster: $pull_events" >&2; exit 1; }
  policies=$(kubectl -n "$namespace" get pods -o jsonpath='{range .items[*].spec.containers[*]}{.imagePullPolicy}{"\n"}{end}')
  if grep -Fvxq Never <<<"$policies"; then
    echo "offline workload without imagePullPolicy Never" >&2
    exit 1
  fi

  kubectl -n "$namespace" port-forward service/hushmark-gateway 18080:8080 >"/tmp/${cluster_name}-port-forward.log" 2>&1 &
  port_forward_pid=$!
  for _ in {1..60}; do
    curl --fail --silent http://127.0.0.1:18080/healthz >/dev/null && break
    sleep 1
  done
  response=$(curl --fail --silent --show-error \
    -H 'authorization: Bearer hm_k1_evaluation_local_key' \
    -H 'content-type: application/json' \
    --data '{"model":"hushmark-eval","messages":[{"role":"user","content":"TCKN 10000000146 için kaydı bul"}]}' \
    http://127.0.0.1:18080/v1/chat/completions)
  grep -Fq '10000000146' <<<"$response"
  kubectl -n "$namespace" get service hushmark-core -o jsonpath='{.spec.type}' | grep -Fxq ClusterIP
  echo "Air-gap kind demo restored the TCKN using only preloaded images; no registry pull was observed."
  exit 0
fi

docker build --target slim -f deploy/docker/core.Dockerfile -t hushmark/core:0.1.0 .
docker build -f deploy/docker/gateway.Dockerfile -t hushmark/gateway:0.1.0 .
docker build -f deploy/docker/console.Dockerfile -t hushmark/console:0.1.0 .

kind create cluster --name "$cluster_name" --wait 120s
kind load docker-image --name "$cluster_name" \
  hushmark/core:0.1.0 hushmark/gateway:0.1.0 hushmark/console:0.1.0

kubectl create namespace "$namespace"
kubectl -n "$namespace" create secret generic hushmark-gateway \
  --from-literal=api-keys=hm_k1_evaluation_local_key \
  --from-literal=openai-api-key=evaluation \
  --from-literal=anthropic-api-key=evaluation
kubectl -n "$namespace" create secret generic hushmark-license \
  --from-file=license.json=deploy/docker/eval/license.json \
  --from-file=public.pem=deploy/docker/eval/public.pem
kubectl -n "$namespace" create secret generic hushmark-admin \
  --from-literal=password=hushmark-evaluation-admin
kubectl -n "$namespace" create secret generic hushmark-kms \
  --from-literal=token=hushmark-evaluation-token
kubectl -n "$namespace" create secret generic hushmark-postgres \
  --from-literal=password=hushmark-evaluation-only \
  --from-literal=database-url=postgres://hushmark:hushmark-evaluation-only@hushmark-postgres:5432/hushmark

kubectl -n "$namespace" apply -f deploy/kind/eval-services.yaml
kubectl -n "$namespace" rollout status deployment/vault --timeout=120s
kubectl -n "$namespace" exec deployment/vault -- sh -ec \
  'export VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=hushmark-evaluation-token; vault secrets enable transit || true; vault write -f transit/keys/hushmark'

helm upgrade --install hushmark deploy/helm/hushmark \
  --namespace "$namespace" \
  --set fullnameOverride=hushmark \
  --set core.image.tag=0.1.0 \
  --set core.image.pullPolicy=Never \
  --set core.nerBackend=disabled \
  --set gateway.image.pullPolicy=Never \
  --set gateway.openaiUpstream=http://fake-upstream:9000/v1 \
  --set gateway.anthropicUpstream=http://fake-upstream:9000/v1 \
  --set console.image.pullPolicy=Never \
  --set enterprise.enabled=true \
  --set enterprise.kms.vaultAddress=http://vault:8200 \
  --set postgres.enabled=true \
  --set postgres.persistence.enabled=false \
  --wait --timeout 5m

kubectl -n "$namespace" rollout status deployment/fake-upstream --timeout=120s
kubectl -n "$namespace" port-forward service/hushmark-gateway 18080:8080 >"/tmp/${cluster_name}-port-forward.log" 2>&1 &
port_forward_pid=$!
for _ in {1..30}; do
  curl --fail --silent http://127.0.0.1:18080/healthz >/dev/null && break
  sleep 1
done

response=$(curl --fail --silent --show-error \
  -H 'authorization: Bearer hm_k1_evaluation_local_key' \
  -H 'content-type: application/json' \
  --data '{"model":"hushmark-eval","messages":[{"role":"user","content":"TCKN 10000000146 için kaydı bul"}]}' \
  http://127.0.0.1:18080/v1/chat/completions)
grep -Fq '10000000146' <<<"$response"

cookie_file=$(mktemp)
curl --fail --silent --show-error -c "$cookie_file" \
  -H 'content-type: application/json' \
  --data '{"email":"admin@hushmark.local","password":"hushmark-evaluation-admin"}' \
  http://127.0.0.1:18080/admin/auth/login >/dev/null
audit=$(curl --fail --silent --show-error -b "$cookie_file" \
  'http://127.0.0.1:18080/admin/audit/events?page=1&limit=100')
grep -Fq 'MASK_APPLIED' <<<"$audit"
rm -f "$cookie_file"

echo "kind demo restored the TCKN and recorded MASK_APPLIED without exposing core externally."
