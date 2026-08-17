# Roadmap

Hushmark is an early `0.1.x` project. This roadmap communicates direction, not a delivery promise.
Priorities may change as evidence and user feedback improve.

## Current priorities

1. **Representative Turkish evaluation** — expand human-reviewed, domain-relevant test sets while
   keeping private or licensed corpora out of the public repository. This is the largest open gap:
   the current benchmark is synthetic and shares a generator with the model's training data, which
   [the engine comparison](docs/benchmark-comparison.md) states plainly. An independent,
   human-written test set is worth more than any further point of measured F1.
2. **Single-host hardening** — gather operational evidence for the Compose production path,
   including backup, recovery, resource, and upgrade procedures.
3. **Streaming coverage** — improve response-side detection and restoration behavior without
   weakening the fail-closed request boundary.
4. **Security evidence** — keep SBOM, provenance, signature, audit-chain, and dependency review
   workflows reproducible for public releases.
5. **Comparison coverage** — add managed PII services to the benchmark harness where credentials
   allow, and keep publishing what could not be measured alongside what could.

## Recently completed

- **Model distribution and provenance.** `hushmark-tr` is published as a public Apache-2.0 model
  repository and consumed by pinned revision with per-file SHA-256 verification. Weights are still
  never committed to Git. See [ADR-0007](docs/adr/ADR-0007-model-distribution.md).
- **Cross-engine measurement.** The benchmark harness now covers competing engines, an LLM redactor,
  and an ablation that separates the model's contribution from the deterministic layer's.

## Later candidates

- Broader provider compatibility and integration examples.
- Additional KMS and identity adapters driven by real deployment demand.
- Usability and accessibility improvements in the operator console.
- More explicit migration and compatibility guarantees as APIs stabilize.

## Non-goals

- Claiming that masking alone is anonymization or legal compliance.
- Sending customer data to a hosted Hushmark service by default.
- Treating synthetic benchmark results as a substitute for representative evaluation.
- Committing adopted model weights or private evaluation corpora to this repository.

Propose changes through the [feature request form](https://github.com/lokomotifai/hushmark/issues/new?template=feature.yml)
and include the user problem, evidence, alternatives, and security impact.
