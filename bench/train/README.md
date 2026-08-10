# hushmark-tr training pipeline

Generated data and checkpoints stay under the ignored `bench/train/outputs/` directory. The
normal workspace lock intentionally installs CPU Torch; CUDA runs must use
[`scripts/bootstrap-gpu.sh`](../../scripts/bootstrap-gpu.sh) and invoke `.venv/bin/python`
directly afterward.

## Reproducible local smoke path

```bash
uv run python bench/train/synthesize.py --profile full --seed 20260809 --check
uv run python bench/train/train.py --smoke
uv run python bench/train/evaluate.py \
  --checkpoint bench/train/outputs/smoke-checkpoint \
  --report bench/train/outputs/smoke-verdict.json
```

Smoke mode uses exactly 200 deterministic examples after the eight repetitions locked by
`hushmark-bench-v0`. It runs one CPU epoch with the transformer encoder frozen. Smoke checkpoints
are never adoption-eligible.

## Full synthetic preparation

```bash
uv run python bench/train/synthesize.py \
  --profile full \
  --output bench/train/outputs/synthetic-full.jsonl
uv run python bench/train/prepare_gliner.py \
  --input bench/train/outputs/synthetic-full.jsonl \
  --source-format synthetic-full \
  --output bench/train/outputs/synthetic-full-gliner.jsonl
```

The `full` profile skips all 2,016 locked evaluation rows before yielding 200,592 balanced
examples. Full training then rejects evaluation-source labels, colliding record IDs, and identical
model-visible content. The earlier `legacy` synthesis profile exists only to reproduce historical
WP-10 evidence and must not be used for a full run.

## AI4Privacy Turkish bootstrap (`net-required`, optional)

The adapter supports the current `pii-masking-openpii-1m` export schema (`source_text`, `language`,
and `privacy_mask` entries with `value`, `start`, `end`, and `label`) as well as the older
`text`/`entities` form. It filters non-Turkish rows, validates values and offsets, maps supported
semantic labels into the closed Hushmark NER taxonomy, and ignores unsupported deterministic
identifier labels.

```bash
uv run python bench/train/prepare_gliner.py \
  --input /approved/path/ai4privacy-tr.jsonl \
  --source-format ai4privacy \
  --output bench/train/outputs/ai4privacy-tr-gliner.jsonl
```

The dataset revision, CC-BY-4.0 attribution, source digest, export filter, and final row count must
be recorded with any run that uses it. External download is not part of required offline tests.

## GPU execution

The guarded full path supports CUDA BF16/FP16 autocast, bounded pilots, atomic checkpoints,
retention, Ctrl-C checkpointing, compatible-run fingerprints, and `--resume-from latest`. A
max-step-limited pilot is mechanically ineligible for adoption. A completed candidate is still
adopted only when full locked-benchmark evaluation improves NER macro strict-F1 by at least 0.05
and no NER type loses more than 0.02 strict-F1.

Use the exact provider settings, transfer controls, pilot/full commands, resume procedure, and
evidence checklist in [`docs/train-runpod.md`](../../docs/train-runpod.md).
