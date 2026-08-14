<div align="center">

# Hushmark

**Turkish-first PII detection, reversible masking, and controlled restoration for AI traffic.**

[![CI](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark/ci.yml?branch=main&label=CI)](https://github.com/lokomotifai/hushmark/actions/workflows/ci.yml)
[![Supply chain](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark/supply-chain.yml?branch=main&label=supply%20chain)](https://github.com/lokomotifai/hushmark/actions/workflows/supply-chain.yml)
[![Release](https://img.shields.io/github/v/release/lokomotifai/hushmark-open-core?label=release)](https://github.com/lokomotifai/hushmark-open-core/releases/latest)
[![License](https://img.shields.io/github/license/lokomotifai/hushmark)](LICENSE)

[English](README.md) · [Türkçe](README.tr.md) · [Documentation](docs/README-dev.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

</div>

Hushmark keeps sensitive Turkish data inside your control boundary before requests reach an AI
provider. It combines deterministic recognizers with a Turkish PII model, applies an explicit
policy, replaces sensitive spans with placeholders, and restores supported responses through a
self-hosted gateway.

> [!IMPORTANT]
> Reversible masking is a technical security measure—not anonymization, legal advice, or a
> compliance guarantee. Detection can miss or misclassify content. Validate Hushmark against
> representative data and keep human and organizational controls in place.

## Why Hushmark

| Without a privacy gateway                          | With Hushmark                                                       |
| -------------------------------------------------- | ------------------------------------------------------------------- |
| Raw identifiers can leave the application boundary | Policy runs before provider forwarding                              |
| Masking behavior is scattered across applications  | Detection, policy, and restoration use one boundary                 |
| Provider logs may contain direct identifiers       | Supported identifiers are replaced by scoped placeholders           |
| Evidence is assembled after an incident            | Audit chaining and Turkish Madde 12 reports can be produced locally |

## What is included

- `core/`: FastAPI detection and masking authority.
- `packages/gateway/`: OpenAI- and Anthropic-compatible proxy with streaming restoration.
- `packages/gateway-enterprise/`: persistent encrypted vault, RBAC, audit chain, offline licensing,
  and Tedbir report. The historical package name remains, but its source is Apache-2.0 licensed.
- `apps/console/`: Turkish/English operator console.
- `packages/sdk-ts/` and `sdk-py/`: typed TypeScript and Python clients.
- `bench/` and `taxonomy/`: reproducible evaluation pipeline and the closed v0.1 entity taxonomy.
- `deploy/`: Docker Compose, Helm, production preflight, and air-gap packaging.

The smaller [hushmark-open-core](https://github.com/lokomotifai/hushmark-open-core) repository is a
source-only release mirror for the detector, gateway, SDKs, benchmark, and taxonomy. This full
repository is the canonical development history; both repositories are licensed under Apache-2.0.

## Data flow

```text
Application
    │ provider-compatible request
    ▼
Hushmark Gateway ──► detector + policy ──► masked request ──► AI provider
    ▲                       │
    └──── restored response┴──── scoped vault / audit evidence
```

Hushmark fails closed when its detection boundary is unavailable. Model output is only one signal;
policy and masking decisions remain outside the model.

## Quick start

Prerequisites: Node.js 22, pnpm 9, Python 3.12, uv, Docker, and enough local memory for the selected
model backend.

```bash
./scripts/bootstrap.sh
./scripts/verify.sh
docker compose -f deploy/docker/compose.yaml -f deploy/docker/compose.dev.yaml up -d
```

The adopted `hushmark-tr` weights are intentionally not stored in Git. Install the separately
distributed, checksum-verified model under `models/hushmark-tr/` before model-backed startup.
Bootstrap never substitutes or regenerates production weights implicitly.

For a single-host production path, start with [production Compose](docs/install-compose-production.md).
Kubernetes users can follow [Helm installation](docs/install-helm.md); disconnected environments can
use the [air-gap guide](docs/install-airgap.md).

## Published artifacts

| Artifact       | Package / image                                                                            |
| -------------- | ------------------------------------------------------------------------------------------ |
| Core           | [`hushmark-core`](https://pypi.org/project/hushmark-core/) · `ghcr.io/hushmark/core:0.1.0` |
| Gateway        | `ghcr.io/hushmark/gateway:0.1.0`                                                           |
| Console        | `ghcr.io/hushmark/console:0.1.0`                                                           |
| Python SDK     | [`hushmark-sdk`](https://pypi.org/project/hushmark-sdk/)                                   |
| TypeScript SDK | [`@hushmark/ai-sdk`](https://www.npmjs.com/package/@hushmark/ai-sdk)                       |
| Shared schemas | [`@hushmark/shared`](https://www.npmjs.com/package/@hushmark/shared)                       |

Release workflows produce provenance and SBOM evidence. Verify image signatures and attestations as
described in the [security model](docs/security.md); do not treat a floating tag as release identity.

## Project status

Hushmark is an early `0.1.x` release. The repository includes synthetic benchmark evidence and
deployment tests, but those results do not establish accuracy on every organization’s traffic.
Known limitations and next priorities are tracked in the [roadmap](ROADMAP.md) and
[model card](docs/model-card-hushmark-tr.md).

## Community and license

Hushmark is maintained in the open under the [Apache License 2.0](LICENSE). Contributions use the
[Developer Certificate of Origin](CONTRIBUTING.md#developer-certificate-of-origin); no CLA is
required. Please read the [Code of Conduct](CODE_OF_CONDUCT.md), [governance model](GOVERNANCE.md),
and [support policy](SUPPORT.md) before participating. The license does not grant trademark rights;
see [TRADEMARKS.md](TRADEMARKS.md).
