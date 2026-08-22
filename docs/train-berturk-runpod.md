# Hushmark BERTurk span-NER training on RunPod

This runbook trains a fixed 12-label span classifier on the immutable
`dbmdz/bert-base-turkish-cased` encoder revision
`b6e1de16c983e0f2c70664591ea3f22810072608`. It reuses the 200,592-row legacy
synthetic corpus and the approved 28,000-row new corpus. Locked test sets are
used only for overlap checks until one development-selected full checkpoint exists.

## Hardware and safety boundary

- RunPod Secure Cloud, On-Demand, one NVIDIA A100 SXM 80 GB.
- 30 GB container disk and 100 GB encrypted Pod Volume at `/workspace`.
- BF16, batch size 32, seed `20260809`.
- 70% legacy replay and 30% new examples per epoch, with label balancing inside each source.
- First run exactly 1,000 optimizer steps. Do not start the full run unless the pilot gate passes.
- Operational spend cap: USD 20. Retrieve and verify artifacts before deleting the Pod.

## Prepare the isolated workspace

Extract and verify the code and data bundles, then create the CUDA environment without fetching
the GLiNER registry models:

```bash
cd /workspace
tar -xzf hushmark-replay-training-0.2.0.tar.gz
tar -xzf hushmark-replay-data-0.2.0.tar.gz

cd /workspace/hushmark-replay-training-0.2.0
python3 scripts/verify-training-bundle.py
cd /workspace/hushmark-replay-data-0.2.0
python3 scripts/verify-training-data-bundle.py

cd /workspace/hushmark-replay-training-0.2.0
python3 -m venv /workspace/.uv-bootstrap
/workspace/.uv-bootstrap/bin/python -m pip install --disable-pip-version-check uv==0.12.3
export PATH=/workspace/.uv-bootstrap/bin:/usr/local/bin:/usr/bin:/bin
HUSHMARK_FETCH_MODELS=0 bash scripts/bootstrap-gpu.sh
bash scripts/bootstrap-gpu.sh --check
.venv/bin/python scripts/fetch-berturk.py --output models/bert-base-turkish-cased
```

## Rebuild the replay corpus

```bash
.venv/bin/python bench/train/synthesize_dev.py \
  --seed 20260809 \
  --output bench/train/outputs/synthetic-dev.jsonl

.venv/bin/python bench/train/synthesize.py \
  --profile full \
  --seed 20260809 \
  --output bench/train/outputs/synthetic-full.jsonl

.venv/bin/python bench/train/prepare_gliner.py \
  --input bench/train/outputs/synthetic-full.jsonl \
  --source-format synthetic-full \
  --output bench/train/outputs/synthetic-full-gliner.jsonl

.venv/bin/python bench/train/prepare_replay.py \
  --legacy bench/train/outputs/synthetic-full-gliner.jsonl \
  --new /workspace/hushmark-replay-data-0.2.0/data/new/train.jsonl \
  --output bench/train/outputs/replay-train.jsonl \
  --manifest bench/train/outputs/replay-train.manifest.json
```

The resulting corpus must contain 228,592 rows, have zero cross-source ID/content overlap, and
require no span wider than 16 words. Training uses a conservative maximum width of 24.

## Run the 1,000-step pilot

```bash
.venv/bin/python bench/train/train_berturk.py \
  --authorized-full-run \
  --data bench/train/outputs/replay-train.jsonl \
  --validation-suite legacy=bench/train/outputs/synthetic-dev.jsonl \
  --validation-suite new=/workspace/hushmark-replay-data-0.2.0/data/new/validation.jsonl \
  --evaluation-suite legacy_locked=bench/data/hushmark-bench-v0.jsonl \
  --evaluation-suite new_locked=/workspace/hushmark-replay-data-0.2.0/data/new/test_locked.jsonl \
  --model-dir models/bert-base-turkish-cased \
  --output bench/train/outputs/a100-berturk-pilot \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 32 \
  --max-length 256 \
  --max-width 24 \
  --max-steps 1000 \
  --validation-every 500 \
  --checkpoint-every 500 \
  --keep-checkpoints 2

.venv/bin/python bench/train/check_berturk_pilot.py \
  --manifest bench/train/outputs/a100-berturk-pilot/training_manifest.json
```

## Run the full candidate only after a passing pilot

```bash
.venv/bin/python bench/train/train_berturk.py \
  --authorized-full-run \
  --data bench/train/outputs/replay-train.jsonl \
  --validation-suite legacy=bench/train/outputs/synthetic-dev.jsonl \
  --validation-suite new=/workspace/hushmark-replay-data-0.2.0/data/new/validation.jsonl \
  --evaluation-suite legacy_locked=bench/data/hushmark-bench-v0.jsonl \
  --evaluation-suite new_locked=/workspace/hushmark-replay-data-0.2.0/data/new/test_locked.jsonl \
  --model-dir models/bert-base-turkish-cased \
  --output bench/train/outputs/a100-berturk-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 32 \
  --max-length 256 \
  --max-width 24 \
  --validation-every 1000 \
  --early-stopping-patience 4 \
  --checkpoint-every 1000 \
  --keep-checkpoints 2
```

Resume an interrupted run by repeating the identical command with `--resume-from latest`.

## Package the selected artifact

```bash
cd /workspace/hushmark-replay-training-0.2.0
tar -czf /workspace/hushmark-berturk-candidate.tar.gz \
  bench/train/outputs/a100-berturk-full/model \
  bench/train/outputs/a100-berturk-full/training_manifest.json \
  bench/train/outputs/a100-berturk-full/development-best/validation_report.json \
  bench/train/outputs/a100-berturk-pilot/training_manifest.json \
  bench/train/outputs/replay-train.manifest.json
sha256sum /workspace/hushmark-berturk-candidate.tar.gz \
  > /workspace/hushmark-berturk-candidate.tar.gz.sha256
```

The candidate remains adoption-ineligible until it is compared with `models/hushmark-tr` on both
locked suites. Do not tune thresholds or hyperparameters after consulting either locked result.
