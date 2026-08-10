# Hushmark

Hushmark is a Turkish-first, on-premise PII detection and reversible masking gateway for LLM
traffic. It detects deterministic Turkish identifiers and model-owned entity spans, applies a
policy before forwarding, and restores placeholders in supported provider responses.

Reversible masking is a technical security measure, not anonymization and not a legal-compliance
guarantee. Detection can miss or misclassify content; evaluate the committed benchmark and your
own representative data before production use.

## Open-core surfaces

- `core/`: FastAPI detection and masking authority.
- `packages/gateway/`: OpenAI and Anthropic compatible proxy with streaming restoration.
- `packages/sdk-ts/` and `sdk-py/`: TypeScript and Python clients.
- `bench/`: reproducible Turkish synthetic benchmark and model pipeline.
- `taxonomy/`: the closed v0.1 entity taxonomy.

The console, persistent encrypted vault, RBAC, audit evidence, offline commercial licensing, and
Tedbir report are enterprise surfaces and are not part of the extracted open-core source tree.

## Start locally

Prerequisites are Node.js 22, pnpm 9, Python 3.12, uv, and Docker.
The adopted `hushmark-tr` artifact is distributed separately from source until AC-2; install the
verified artifact under `models/hushmark-tr/` or use the air-gap bundle. Bootstrap verifies its
pinned FP32 ONNX graph and never regenerates a production model implicitly.

```bash
./scripts/bootstrap.sh
./scripts/verify.sh
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml up -d
```

See [Compose installation](docs/install-compose.md), [Helm installation](docs/install-helm.md),
[air-gap installation](docs/install-airgap.md), and the [security model](docs/security.md).

## License intent

Each package carries its own license file. Open-core packages are Apache-2.0-intended. Enterprise
packages remain proprietary. No repository or package has been externally published as part of
the local v0.1.0 release-candidate work.
