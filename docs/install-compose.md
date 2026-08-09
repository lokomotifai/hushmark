# Install with Docker Compose

Use Compose for a single-host evaluation or controlled internal deployment. The evaluation stack
contains PostgreSQL, Vault dev mode, core, gateway, console, and a local fake provider. Vault dev
mode and the bundled evaluation credentials are not production configuration.

## Prerequisites

- Docker Engine with Compose v2.
- At least 8 GiB available memory for the ONNX model stack.
- No host ports 3000 or 8080 already in use.

## Evaluation

```bash
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml up -d --build
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml ps
curl --fail http://127.0.0.1:8080/readyz
```

Send a request with the evaluation key:

```bash
curl --fail --show-error \
  -H 'authorization: Bearer hm_k1_evaluation_local_key' \
  -H 'content-type: application/json' \
  --data '{"model":"hushmark-eval","messages":[{"role":"user","content":"TCKN 10000000146 için kaydı bul"}]}' \
  http://127.0.0.1:8080/v1/chat/completions
```

The fake upstream receives placeholders; the client response contains the restored value. Stop and
remove evaluation state with the exact Compose files:

```bash
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml down -v
```

## Production changes

Replace every evaluation secret, use a persistent non-dev Vault/KMS target, configure PostgreSQL
backups, pin image digests, restrict host/network access, provide an issued license, and route only
approved provider endpoints. Keep core private to the service network.
