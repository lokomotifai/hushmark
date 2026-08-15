# Install with Helm

The chart supports a ClusterIP-only core, gateway, optional console, optional enterprise features,
and optional bundled PostgreSQL. For production, use externally managed secrets and normally an
externally operated PostgreSQL service.

## Validate and render

```bash
helm lint deploy/helm/hushmark
helm template hushmark deploy/helm/hushmark --namespace hushmark
```

## Required secrets

Create the gateway secret before installation. The secret keys are configurable in `values.yaml`.

```bash
kubectl create namespace hushmark
kubectl -n hushmark create secret generic hushmark-gateway \
  --from-literal=api-keys='hm_k1_replace_with_at_least_16_chars' \
  --from-literal=core-service-token='replace-with-at-least-32-random-characters' \
  --from-literal=openai-api-key='replace' \
  --from-literal=anthropic-api-key='replace'
```

For enterprise mode, also create the license/public-key, database, admin, audit-HMAC, and KMS
secrets named by the chart values. Do not place plaintext secret values in a committed values file.
The enterprise process applies packaged database migrations under a PostgreSQL advisory lock at
startup. The security-hardening migration intentionally deletes legacy, tenantless vault rows;
drain active conversations before upgrading from an earlier v0.1.0 checkout.

## Install

```bash
helm upgrade --install hushmark deploy/helm/hushmark \
  --namespace hushmark \
  --set core.image.repository=internal.example/hushmark/core \
  --set core.image.tag=0.1.0-model \
  --set gateway.image.repository=internal.example/hushmark/gateway \
  --set gateway.image.tag=0.1.0 \
  --wait --timeout 10m
```

Verify `deployment/hushmark-core` and `deployment/hushmark-gateway` readiness. Expose only the
gateway through an authenticated internal ingress. The core Service must remain `ClusterIP`.
When NetworkPolicy is enabled, label the ingress controller namespace with
`hushmark.ai/gateway-access=true`; only that namespace and the Hushmark console pods may reach the
gateway.

## Shared-cluster release

`values.shared.yaml` pins the three published v0.1.0 GHCR images by their verified manifest
digests. It deploys the open-core core and gateway only; the console, enterprise features, and
bundled PostgreSQL remain disabled.

The published core image is intentionally model-free. Before deployment, create and populate an
encrypted persistent volume claim named `hushmark-models`. The claim must expose this exact layout
read-only to the core workload:

```text
/models/hushmark-tr/gliner_config.json
/models/hushmark-tr/model.onnx
/models/hushmark-tr/tokenizer.json
/models/hushmark-tr/tokenizer_config.json
```

Verify the local model checksum against the adopted release evidence before copying it to the
volume. Do not publish the model directory to the public container registry.

The manual `Deploy shared Kubernetes` workflow has two modes. `plan` validates and renders without
cluster credentials. `apply` uses the protected `shared-production` GitHub environment and requires
these environment secrets:

- `KUBE_CONFIG_B64`: base64-encoded kubeconfig scoped to the target namespace.
- `HUSHMARK_API_KEYS`: one or more gateway keys accepted by the open-core gateway.
- `HUSHMARK_OPENAI_API_KEY`: optional upstream credential.
- `HUSHMARK_ANTHROPIC_API_KEY`: optional upstream credential.

Create the namespace and bound model PVC before selecting `apply`. The workflow reconciles only the
gateway Secret and the Helm release, uses `--atomic`, waits for both rollouts, and verifies gateway
readiness through a temporary port-forward. Keep environment approval protection enabled so a
rendered plan can be reviewed before cluster mutation.

See [configuration](config.md) for runtime settings and [security](security.md) for trust
boundaries and production controls.
