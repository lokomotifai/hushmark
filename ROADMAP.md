# Roadmap

Hushmark is an early `0.1.x` project. This roadmap communicates direction, not a delivery promise.
Priorities may change as evidence and user feedback improve.

## Current priorities

1. **Representative Turkish evaluation** — expand human-reviewed, domain-relevant test sets while
   keeping private or licensed corpora out of the public repository.
2. **Model distribution and provenance** — document a repeatable, checksum-verified path for the
   adopted model artifact without committing weights to Git.
3. **Single-host hardening** — gather operational evidence for the Compose production path,
   including backup, recovery, resource, and upgrade procedures.
4. **Streaming coverage** — improve response-side detection and restoration behavior without
   weakening the fail-closed request boundary.
5. **Security evidence** — keep SBOM, provenance, signature, audit-chain, and dependency review
   workflows reproducible for public releases.

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

Propose changes through the [feature request form](https://github.com/hushmark/hushmark/issues/new?template=feature.yml)
and include the user problem, evidence, alternatives, and security impact.
