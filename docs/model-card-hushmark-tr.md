# Model card: hushmark-tr

## Status

`hushmark-tr` is the locally adopted v0.1 production NER model. The guarded AC-1 retry on
2026-08-10 passed the isolated development gate, the locked adoption gate, and FP32 ONNX parity.
It replaces `urchade/gliner_multi_pii-v1` as the local runtime default. The model and release
artifacts have not been uploaded or published; external distribution remains behind AC-2.

## Intended use

The model proposes spans for the 12 NER-owned Hushmark entity types: person, address, organization,
date of birth, health, religion, ethnicity, political opinion, sexual life, criminal record,
biometric reference, and union membership. Deterministic identifiers and secrets remain owned by
the L0 validators. Policy, masking, blocking, and audit decisions are outside the model.

This model is a detection aid and not an anonymization or legal-compliance guarantee. False
negatives and false positives remain possible; operators must validate it on their own data.

## Architecture and context

The checkpoint fine-tunes the GLiNER `gliner_multi_pii-v1` architecture and its pinned
mDeBERTa-v3-base encoder. The training and runtime configuration limits inputs to 384 tokens and
spans to 12 tokens. Production uses the verified FP32 ONNX graph; the retained Torch checkpoint is
the reproducibility and reference path.

## Data provenance

- Locked evaluation: seeded synthetic `hushmark-bench-v0`, 2,016 rows, SHA-256
  `6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642`. It was evaluated once,
  after candidate selection, and was never used for training or threshold selection.
- Isolated development set: 1,008 synthetic rows immediately after the locked repetition range.
  Raw SHA-256 `2525360ff36e613a967389b1ff7f8522f5861c2b43fc044387e7a8dc71c08a5e`;
  prepared SHA-256 `8da126adf23c9ea54e4fc09eb62a9c7ce8897f753d5c1724f2bb862370c11880`.
- Full training set: 200,592 deterministic, balanced synthetic examples generated after both the
  locked and development ranges. Raw SHA-256
  `4e622b794b670b32b8dd274ccfb2164b13ea73f93c2d01aba382b25f60066e9d`;
  prepared SHA-256 `849256b4c1cfb6b243c377e97abeafe65372ffe69fe868d4c5c0f232acce8a43`.
- No private strategy corpus, customer data, LLM synthesis, or external dataset was used.

The sources share a synthetic template family, but row IDs, source labels, and model-visible
content are disjoint. This prevents direct leakage; it does not make the benchmark representative
of real customer language.

## Training configuration

The successful retry used one NVIDIA A100-SXM4-80GB, BF16, batch size 16, seed 20260809, a frozen
encoder, head learning rate `1e-5`, 50 warm-up steps, linear decay, balanced sampling, validation
every 100 steps, minimum development improvement 0.002, and patience 5. Training started from the
pinned base model, selected the atomic best checkpoint at step 1,500, and stopped cleanly at step
2,000 after 930.497 seconds. Peak allocated GPU memory was 1,526,949,888 bytes.

The selected Torch weight is 1,155,879,495 bytes with SHA-256
`a8f8bc87fdd4d4a92898513fd87eed9e7ccd2b6603ef1d1d5ce152e49192b6c2`. Its run fingerprint is
`edf3666702a036f6b9906da451361c771082b89c9febb2bc3306e352d614bf1d`.

An earlier three-epoch AC-1 attempt used a substantially larger learning rate and no development
selection. It collapsed to zero accepted NER spans on the locked benchmark and was rejected. That
failure remains in the evidence history; its checkpoint was not promoted.

## Evaluation and adoption

Adoption requires a complete development-selected full run, at least +0.05 absolute NER macro
strict-F1 over the incumbent, and no per-type regression greater than 0.02.

The retry's development macro strict-F1 improved from 0.638278 at step 0 to 0.994642 at the
selected checkpoint with no per-type regression. The once-only locked verdict then reported:

- candidate NER macro strict-F1: `0.9941238343`
- incumbent NER macro strict-F1: `0.0796138809`
- absolute improvement: `+0.9145099534`
- per-type regressions over 0.02: none
- machine verdict: `adopt=true`, `eligible=true`, `technical_pass=true`

The weakest locked NER type scores were `SEXUAL_LIFE=0.973262`, `ORG=0.981723`,
`PERSON=0.984954`, and `ADDRESS=0.989547`; the remaining NER types scored 1.0 on this synthetic
benchmark.

## ONNX deployment evidence

The supported GLiNER export API produced an opset-19 FP32 graph, 1,157,113,250 bytes, SHA-256
`c5e72ca974f2e671325314f5a2d1d7eb2e1951ccd3d5250b0e223787f22c35ed`. Development-only
calibration selected an effective ONNX threshold of 0.4. On all 1,008 development rows, FP32 ONNX
macro strict-F1 was `0.993782469`, only `-0.000859107` from Torch; the sole per-type decline was
`POLITICAL=-0.0103093`, within the 0.02 limit.

Dynamic INT8 quantization was explicitly rejected: its best development macro strict-F1 was only
`0.413555` even after threshold calibration. `model_quantized.onnx` is evidence only and is not
shipped in the active model directory or production image.

On the local Apple ARM64 verification host, one warmed semantic sentence that forced NER measured
44.74 ms median and 45.41 ms maximum across five FP32 ONNX predictions. This is a functional
capacity tripwire for that host, not a cross-platform throughput guarantee.

## Limitations

The benchmark is synthetic and template-adjacent to training. It does not cover every Turkish
dialect, spelling error, OCR artifact, code-switching pattern, or organization-specific document.
Rare special-category entities have limited lexical diversity. Inputs beyond the configured
384-token context are truncated by the model. FP32 ONNX is materially larger and slower than INT8;
the deterministic residual short circuit avoids invoking it for inputs fully handled by L0, but
capacity must still be validated on representative unknown residuals. Human-curated and
customer-specific evaluation remains required future evidence.

## License and release

The upstream GLiNER model is Apache-2.0 and the pinned mDeBERTa base is MIT. The locally retained
model is derived only from those components and Hushmark-generated synthetic data. Exact artifact
hashes are pinned in `core/models.yaml`. No model weight, image, package, or registry artifact was
published externally during AC-1.
