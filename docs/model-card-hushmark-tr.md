# Model card: hushmark-tr

## Status

`hushmark-tr` is a reproducible candidate pipeline, not the v0.1 production model. The production
runtime continues to use the pinned `urchade/gliner_multi_pii-v1` incumbent until a full checkpoint
passes the machine-readable adoption rule. The paid/GPU run is pending AC-1 authorization.

## Intended use

The model proposes spans for the 12 NER-owned Hushmark entity types: person, address, organization,
date of birth, health, religion, ethnicity, political opinion, sexual life, criminal record,
biometric reference, and union membership. Deterministic identifiers and secrets remain owned by
the L0 validators. Policy, masking, blocking, and audit decisions are outside the model.

This model is a detection aid and not an anonymization or legal-compliance guarantee. False
negatives and false positives are expected; operators must validate policy and benchmark evidence
for their own data.

## Data provenance

- Required local source: seeded synthetic `hushmark-bench-v0`, whose lock digest is committed.
- Scaled source: 200,592 deterministic examples, balanced across six domains, four morphology
  modes, and every domain/morphology intersection.
- Optional source: an approved Turkish AI4Privacy export. Network access, dataset terms, exact
  revision, source digest, and scale remain pending and must be recorded before a full run.
- No private strategy corpus or customer data is a training source.

## Training configuration

The base model and tokenizer are resolved from the offline pinned registry. Smoke mode uses 200
seeded examples drawn after the eight repetitions reserved for the locked benchmark, one CPU
epoch, and a frozen transformer encoder; it updates the remaining GLiNER NER layers and writes
weights plus a manifest. Full mode rejects records marked as originating from the evaluation
benchmark. Full-run hyperparameters, hardware, energy/time, dataset hashes, and output digest
remain pending AC-1.

## Evaluation and adoption

Evaluation uses strict type plus Unicode code-point offsets on the locked 2,016-example
`hushmark-bench-v0`. Only a full, complete evaluation is eligible. Adoption requires both:

1. NER macro strict-F1 improves by at least 0.05 absolute over the incumbent.
2. No NER entity type regresses by more than 0.02 strict-F1.

Smoke checkpoints are expected to produce `adopt=false`; their purpose is to prove that data,
training, checkpoint loading, inference, benchmark evaluation, and verdict generation connect.

### Recorded CPU smoke result — 2026-08-10

The local ARM64 CPU run trained 200 non-overlapping synthetic holdout rows for one epoch in
28.984 seconds. The saved checkpoint reloaded with its manifest SHA-256 and evaluated all 2,016
locked examples in 230.395 seconds. It measured NER macro strict-F1 0.8126 versus the incumbent's
0.0796 and no per-type regression over 0.02, so the technical threshold calculation passed. The
machine verdict remained `adopt=false` and `eligible=false` because smoke artifacts can never be
adopted. The large gain is template-adjacent synthetic evidence, not proof of real-world
generalization; it does not change the production model.

## Limitations

The required benchmark is synthetic and does not represent every Turkish dialect, spelling,
OCR error, code-switching pattern, or organizational document. Rare special-category entities have
limited lexical diversity. GLiNER truncates long inputs according to its configured maximum length.
Human-curated and customer-specific evaluation remains separate future evidence.

## License and release

The incumbent GLiNER model is Apache-2.0 and the pinned mDeBERTa tokenizer/model is MIT. A final
`hushmark-tr` release requires provenance review for every added dataset and a completed model-card
license section. No model weights are published or externally uploaded without AC-2 authorization.
