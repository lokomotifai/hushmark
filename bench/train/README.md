# hushmark-tr training pipeline

The pipeline is offline by default and keeps generated data and checkpoints under the ignored
`bench/train/outputs/` directory.

## Reproducible local path

```bash
uv run python bench/train/synthesize.py --seed 20260809 --check
uv run python bench/train/prepare_gliner.py \
  --input bench/data/hushmark-bench-v0.jsonl \
  --source-format hushmark \
  --output bench/train/outputs/gliner-v0.jsonl
uv run python bench/train/train.py --smoke
uv run python bench/train/evaluate.py \
  --checkpoint bench/train/outputs/smoke-checkpoint \
  --report bench/train/outputs/smoke-verdict.json
```

Smoke mode uses exactly 200 deterministic examples from the repetitions immediately after the
eight repetitions locked by `hushmark-bench-v0`; no exact evaluation row enters training. It runs
one CPU epoch, freezes the transformer encoder while updating GLiNER's trainable NER layers, and
rejects a run taking ten minutes or longer. A smoke checkpoint is never adoption-eligible even
when it is evaluated on the full bench. Full mode rejects prepared rows whose source is the locked
evaluation benchmark.

## AI4Privacy Turkish bootstrap (`net-required`)

External dataset download is intentionally outside required tests. After the dataset's terms and
the network operation are approved, export its Turkish subset as JSONL with `text` (or
`source_text`), `language`, and `entities` (or `spans`). Every entity must contain a character
`start`, `end`, and `type`/`label`. Then run:

```bash
uv run python bench/train/prepare_gliner.py \
  --input /approved/path/ai4privacy-tr.jsonl \
  --source-format ai4privacy \
  --output bench/train/outputs/ai4privacy-tr-gliner.jsonl
```

The adapter filters non-Turkish rows, maps the documented identity/address/organization/date and
health aliases into the closed Hushmark NER taxonomy, rejects misaligned offsets, and ignores
unsupported labels. The source file, license evidence, and dataset digest must be recorded in the
full-run model card before AC-1 is exercised.

Full training is guarded by `--authorized-full-run`, requires an explicit prepared `--data` file,
and remains pending AC-1. The evaluator adopts a full checkpoint only when its NER macro strict-F1
beats the incumbent by at least 0.05 and no NER type loses more than 0.02 strict-F1.
