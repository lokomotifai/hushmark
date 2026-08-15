# Changelog

All notable changes are recorded here. The project follows a fixed product version across its
packages and uses semantic versioning before 1.0 with breaking changes permitted on minor bumps.

## Unreleased

- Made the NER model selectable end to end: registry-validated `HUSHMARK_CORE_MODEL_ID` with
  clear errors, `core.modelId` Helm value, parameterized production Compose, selectable-model
  listing on `GET /v1/metadata`, and a new model selection guide (`docs/models.md`).
- Added `LiquidAI/LFM2.5-Encoder-350M-PII-Detector` as an opt-in remote model on a new offline
  token-classification backend with BIOES decoding; its pinned remote code is SHA-256-verified
  before execution and the weights are never redistributed.
- Extended `scripts/fetch-models.py` with per-model selection, tokenizer dependency expansion,
  and upstream license notices; models marked `optional` are no longer fetched implicitly.

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
