# Changelog

All notable changes are recorded here. The project follows a fixed product version across its
packages and uses semantic versioning before 1.0 with breaking changes permitted on minor bumps.

## Unreleased

- Added competitor benchmark adapters: bare GLiNER, Presidio configured for Turkish, and an
  OpenAI LLM redactor whose spans are resolved against the source text instead of trusting
  model-reported offsets.
- Added decision-grade benchmark slices: per-example latency percentiles, Turkish morphology
  recall, KVKK m.6 special-category recall, and entity-type coverage.
- Added a cross-engine comparison renderer and `docs/benchmark-comparison.md`.
- Pointed the `hushmark-tr` registry entry at the published `lokomotifai/hushmark-tr-289m`
  repository so the pinned weights and ONNX export are fetchable and reproducible.
- Fixed model bootstrap reformatting the materialized runtime config, which made its bytes
  diverge from the pinned source and failed the runtime integrity check on every Torch load.

## 0.1.1 — 2026-08-15

- Fixed private-key ReDoS, Unicode digit bypasses, masking complexity, and request-size abuse.
- Made core authentication fail closed and added bounded upstream streaming and response handling.
- Enforced tenant policies at runtime and hardened vault key, placeholder, and login concurrency.
- Made enterprise audit HMAC mandatory and added an external append-only head checkpoint.
- Hardened console CSRF/cookies/CSP, SDK transport validation, model integrity, and deployment policy.
- Pinned CI actions and installers, restricted immutable releases to `main`, and added mirror
  secret/supply-chain gates.

## 0.1.0 — 2026-08-10

- Added the 24-type Turkish entity taxonomy and cross-language code generation.
- Added deterministic validators, offline Torch/ONNX NER, reversible masking, and strict offsets.
- Added OpenAI and Anthropic buffered/streaming gateway paths with fail-closed policy behavior.
- Added TypeScript and Python SDKs plus runnable integration examples.
- Added enterprise policy persistence, KMS envelope vault, RBAC, audit chain, and offline licensing.
- Added Turkish-first console, English fallback, and Madde 12 Tedbir PDF evidence.
- Added reproducible benchmark, model-training smoke pipeline, Docker/Compose/Helm packaging,
  signed-image/SBOM workflows, performance gates, and local release tooling.

The open-core source, SDK packages, and signed container images are released through the Lokomotif
AI GitHub organization. Model weights remain a separately verified artifact and are never fetched
implicitly by production startup.
