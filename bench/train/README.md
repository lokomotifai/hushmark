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

Smoke mode uses exactly 200 deterministic examples after both the eight repetitions locked by
`hushmark-bench-v0` and the four repetitions reserved for development. It runs one CPU epoch with
the transformer encoder frozen. Smoke checkpoints are never adoption-eligible.

## Full synthetic preparation

```bash
uv run python bench/train/synthesize_dev.py \
  --output bench/train/outputs/synthetic-dev.jsonl
uv run python bench/train/synthesize.py \
  --profile full \
  --output bench/train/outputs/synthetic-full.jsonl
uv run python bench/train/prepare_gliner.py \
  --input bench/train/outputs/synthetic-full.jsonl \
  --source-format synthetic-full \
  --output bench/train/outputs/synthetic-full-gliner.jsonl
```

The development profile reserves 1,008 rows immediately after the 2,016 locked evaluation rows.
The `full` profile skips both ranges before yielding 200,592 examples. Full training rejects
evaluation/development source labels, colliding record IDs, and identical model-visible content.
The earlier `legacy` synthesis profile exists only to reproduce historical WP-10 evidence and must
not be used for a full run.

## Legacy/new replay preparation

The next `hushmark-tr` candidate uses the same 200,592-row `synthetic-full` corpus plus the approved
new prepared train split. `prepare_replay.py` rejects source mismatches, duplicate IDs, and
cross-source content overlap before writing a digest-bound union. GPU sampling then fixes each
epoch to 70% legacy and 30% new rows, with label balancing inside each source. Legacy and new
validation suites remain separate in reports and are combined only from exact span counts.

Both the old locked benchmark and the new locked split are supplied to training only as isolation
sets. Neither is used for checkpoint selection or tuning. The final candidate must first pass the
old locked verdict, then beat the incumbent on the new PERSON/ADDRESS/DOB holdout without adding
false positives on empty-gold documents.

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

The guarded full path freezes the text encoder by default, uses separate encoder/head learning
rates when it is deliberately unfrozen, applies warm-up plus linear decay, caps rare-label
oversampling, and evaluates NER-only development metrics every 100 steps. It atomically retains the
best development checkpoint and stops early after five non-improving validations. A max-step pilot
is mechanically ineligible. A full checkpoint becomes final-evaluation eligible only when its
development result improves NER macro strict-F1 by at least 0.05 with no per-type loss over 0.02;
the same binding rule is then applied once to the locked benchmark.

Use the exact provider settings, transfer controls, pilot/full commands, resume procedure, and
evidence checklist in [`docs/train-runpod.md`](../../docs/train-runpod.md).
