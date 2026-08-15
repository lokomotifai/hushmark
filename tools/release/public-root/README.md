<div align="center">

# Hushmark Open Core

**The source-only detector, gateway, SDK, benchmark, and taxonomy release for Hushmark.**

[![CI](https://img.shields.io/github/actions/workflow/status/lokomotifai/hushmark-open-core/ci.yml?branch=main&label=CI)](https://github.com/lokomotifai/hushmark-open-core/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/lokomotifai/hushmark-open-core?label=release)](https://github.com/lokomotifai/hushmark-open-core/releases/latest)
[![License](https://img.shields.io/github/license/lokomotifai/hushmark-open-core)](LICENSE)

[English](README.md) · [Türkçe](README.tr.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

</div>

Hushmark keeps sensitive Turkish data inside your control boundary before requests reach an AI
provider. It detects deterministic identifiers and model-owned spans, applies an explicit policy,
masks supported values with scoped placeholders, and restores supported provider responses.

> [!IMPORTANT]
> Reversible masking is a technical security measure—not anonymization, legal advice, or a
> compliance guarantee. Detection can miss or misclassify content. Evaluate Hushmark against
> representative data before production use.

## What this repository is

This repository is an allowlist-generated, source-only release mirror of the public runtime in
[`lokomotifai/hushmark`](https://github.com/lokomotifai/hushmark), the canonical development repository.
It contains no adopted model weights, private evaluation corpora, console, persistent vault, RBAC,
audit evidence, license issuer, or deployment secrets.

| Path                     | Purpose                                               |
| ------------------------ | ----------------------------------------------------- |
| `core/`                  | FastAPI Turkish PII detection and masking authority   |
| `packages/gateway/`      | OpenAI- and Anthropic-compatible gateway              |
| `packages/sdk-ts/`       | TypeScript client helpers                             |
| `sdk-py/`                | Python client                                         |
| `packages/shared/`       | Public schemas and taxonomy types                     |
| `bench/` and `taxonomy/` | Synthetic benchmark pipeline and closed v0.1 taxonomy |

## Verify the source tree

Prerequisites: Node.js 22, pnpm 10, Python 3.12, and uv.

```bash
git clone https://github.com/lokomotifai/hushmark-open-core.git
cd hushmark-open-core
./scripts/bootstrap.sh
./scripts/verify.sh
```

The adopted `hushmark-tr` model is distributed separately and verified by checksum. It is not
downloaded or regenerated implicitly. Tests that require production weights are clearly reported
and omitted from the source-only verification path.

Published clients and runtime packages can be installed independently:

```bash
pip install hushmark-core hushmark-sdk
npm install @hushmark/ai-sdk @hushmark/shared
```

See [`core/README.md`](core/README.md), [`sdk-py/README.md`](sdk-py/README.md), and
[`packages/sdk-ts/README.md`](packages/sdk-ts/README.md) for component use. Full Compose, production,
and console deployment sources live in the canonical repository.

## Release boundary

The extraction test refuses symlinks, private path names, model outputs, and a private corpus canary.
The exact release boundary is code-reviewed in `tools/release` in the canonical repository. This
mirror should never be used as a destination for private data or model artifacts.

## Project status

Hushmark is an early `0.1.x` release. Synthetic benchmark evidence is useful for regression testing,
not proof of accuracy on every organization’s traffic. Review the [model card](docs/model-card-hushmark-tr.md),
[security model](docs/security.md), and [roadmap](ROADMAP.md) before adoption.

## Community and license

The source is available under the [Apache License 2.0](LICENSE). Code changes should target the
canonical repository so they are preserved by the next extraction; mirror-specific documentation
and community fixes may be proposed here. See [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md).
