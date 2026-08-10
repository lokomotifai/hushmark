# Changelog

All notable changes are recorded here. The project follows a fixed product version across its
packages and uses semantic versioning before 1.0 with breaking changes permitted on minor bumps.

## 0.1.0 — 2026-08-10

- Added the 24-type Turkish entity taxonomy and cross-language code generation.
- Added deterministic validators, offline Torch/ONNX NER, reversible masking, and strict offsets.
- Added OpenAI and Anthropic buffered/streaming gateway paths with fail-closed policy behavior.
- Added TypeScript and Python SDKs plus runnable integration examples.
- Added enterprise policy persistence, KMS envelope vault, RBAC, audit chain, and offline licensing.
- Added Turkish-first console, English fallback, and Madde 12 Tedbir PDF evidence.
- Added reproducible benchmark, model-training smoke pipeline, Docker/Compose/Helm packaging,
  signed-image/SBOM workflows, performance gates, and local release tooling.

The open-core source, SDK packages, and signed container images are released through the Hushmark
GitHub organization. Model weights remain a separately verified artifact and are never fetched
implicitly by production startup.
