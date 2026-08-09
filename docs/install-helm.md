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
  --from-literal=openai-api-key='replace' \
  --from-literal=anthropic-api-key='replace'
```

For enterprise mode, also create the license/public-key, database, admin, and KMS secrets named by
the chart values. Do not place plaintext secret values in a committed values file.

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

See [configuration](config.md) for runtime settings and [security](security.md) for trust
boundaries and production controls.
