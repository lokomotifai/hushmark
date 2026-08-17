# ADR-0007: Model weights are distributed by pinned revision and digest, never in Git

- Status: Accepted
- Date: 2026-08-13
- Supersedes: the local-artifact distribution used during model adoption
- Scope: core, build, release

## Context

The adopted detection model, `hushmark-tr`, is a GLiNER checkpoint fine-tuned from
`urchade/gliner_multi_pii-v1` on an mDeBERTa-v3-base encoder. The Torch weight is about 1.16 GB and
the FP32 ONNX export is a similar size.

Files of that size do not belong in Git. They also cannot be treated casually: the model is a
security-relevant component, and a substituted checkpoint is a detection failure that no test in the
repository would notice unless the repository is checking.

During adoption the weights were handled as a locally delivered artifact, which was safe but made
the project difficult for anyone else to run.

## Decision

Weights are published as a public Apache-2.0 model repository,
[`lokomotifai/hushmark-tr-289m`](https://huggingface.co/lokomotifai/hushmark-tr-289m), and consumed
by pin. `core/models.yaml` records the source repository, an exact revision, and a SHA-256 digest
and byte size for every file, including the ONNX export and its opset.

`scripts/fetch-models.py` downloads the pinned revision and verifies each file against its digest.
`scripts/bootstrap.sh` runs it by default and can be skipped with `HUSHMARK_FETCH_MODELS=0`. The
runtime verifies the model digest at load time, so a mismatch is a startup failure rather than a
quiet fallback.

Container images remain model-free. Weights are mounted or baked in deliberately by the operator,
and the air-gap bundle carries them as a verified payload.

## Alternatives considered

**Git LFS.** Rejected. It puts a gigabyte-scale binary in the clone path of everyone who only wants
to read the gateway, and LFS availability becomes a dependency of `git clone`.

**Downloading whatever is at the model repository's default branch.** Rejected. It means the
detection behavior of a pinned Hushmark version can change without a Hushmark release, which is
exactly the property a pinned version is supposed to prevent.

**Keeping local-artifact distribution.** Rejected once the checkpoint was ready to publish. It made
reproducing the benchmark impossible for anyone outside the project, which undermines the point of
publishing the benchmark.

**Shipping the int8 quantized ONNX export.** Rejected on evidence. Its best development macro strict
F1 was `0.413555` even after threshold calibration, against `0.993782` for FP32. The quantized file
is retained as evidence and is not shipped in the active model directory or the production image.

## Consequences

The first bootstrap downloads a large artifact, and the guides say so along with the disk and memory
requirements. Air-gapped installations use the bundle instead.

Upgrading the model is a deliberate change to `core/models.yaml` with a new revision and new
digests, reviewable as a diff. Model adoption itself has an evidence gate documented in the
[model card](../model-card-hushmark-tr.md): a development-selected full run, at least +0.05 absolute
NER macro strict F1 over the incumbent, and no per-type regression above 0.02.

## Security and privacy impact

Digest pinning makes model substitution detectable at fetch time and at load time. Publishing under
Apache-2.0 with a stated base model and training data provenance lets a reviewer evaluate the model
rather than trust it, and it makes the published benchmark independently reproducible.

Training used only Hushmark-generated synthetic data. No customer data, private strategy corpus, or
external dataset was involved, and that is recorded in the model card rather than only asserted
here.
