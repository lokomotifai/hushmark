# Hushmark replay training on RunPod

This runbook trains the next `hushmark-tr` candidate from the pinned
`gliner_multi_pii-v1` base. It reuses the 200,592-row legacy synthetic corpus and adds the
approved 28,000-row new corpus. It does not publish or register a model automatically.

## Fixed configuration

- RunPod Secure Cloud, On-Demand, one A100 80 GB GPU.
- Official RunPod PyTorch image with full SSH.
- 100 GB encrypted Pod Volume mounted at `/workspace`; do not use an unencrypted Network Volume.
- Python 3.12 and the CUDA Torch wheel pinned by `scripts/bootstrap-gpu.sh`.
- Frozen text encoder, batch size 16, automatic BF16/FP16, seed `20260809`.
- Each epoch contains 70% legacy replay and 30% new examples. Label balancing happens separately
  inside both sources.
- Checkpoints and validation every 100 optimizer steps, with two recoverable checkpoints retained.
- A 500-step pilot must pass the machine gate before the full run is allowed.

The live GPU price and availability must be checked immediately before Pod creation. Storage is
also billable while the Pod exists. Set a RunPod cost alert and terminate the Pod after local
artifact verification.

## 1. Build two local transfer archives

The code bundle is source-only. The data bundle contains only the approved new train, validation,
and locked-test views plus governance evidence. It excludes research sources, public-document
corpora, model weights, generated legacy data, and Git metadata.

```bash
UV_CACHE_DIR=/tmp/hushmark-uv-cache uv run python scripts/build-training-bundle.py
UV_CACHE_DIR=/tmp/hushmark-uv-cache uv run python scripts/build-training-data-bundle.py
shasum -a 256 \
  dist/hushmark-replay-training-0.2.0.tar.gz \
  dist/hushmark-replay-data-0.2.0.tar.gz
```

Generate a task-specific SSH key instead of reusing a personal key. Add its public half to the Pod
and keep the private half only until artifacts have been retrieved.

```bash
mkdir -p /tmp/hushmark-runpod-ssh
ssh-keygen -q -t ed25519 -N '' \
  -f /tmp/hushmark-runpod-ssh/id_ed25519 \
  -C hushmark-replay-training
```

Transfer both archives using the exact public IP and SSH port shown by RunPod:

```bash
scp -i /tmp/hushmark-runpod-ssh/id_ed25519 -P RUNPOD_SSH_PORT \
  dist/hushmark-replay-training-0.2.0.tar.gz \
  dist/hushmark-replay-data-0.2.0.tar.gz \
  root@RUNPOD_PUBLIC_IP:/workspace/
```

## 2. Verify before executing transferred code

```bash
cd /workspace
tar -xzf hushmark-replay-training-0.2.0.tar.gz
tar -xzf hushmark-replay-data-0.2.0.tar.gz

cd /workspace/hushmark-replay-training-0.2.0
python3 scripts/verify-training-bundle.py

cd /workspace/hushmark-replay-data-0.2.0
python3 scripts/verify-training-data-bundle.py
```

Stop if either verifier fails. Never copy customer prompts, credentials, production personal data,
or the private research corpus to the Pod.

## 3. Bootstrap the pinned CUDA environment

```bash
cd /workspace/hushmark-replay-training-0.2.0
python3 -m venv /workspace/.uv-bootstrap
/workspace/.uv-bootstrap/bin/python -m pip install --disable-pip-version-check uv==0.12.3
export PATH=/workspace/.uv-bootstrap/bin:/usr/local/bin:/usr/bin:/bin
bash scripts/bootstrap-gpu.sh
bash scripts/bootstrap-gpu.sh --check
```

The bootstrap downloads the registry-pinned GLiNER base and tokenizer, verifies their SHA-256
digests, and installs the reviewed CUDA Torch wheel. Afterward invoke `.venv/bin/python` directly;
do not run `uv run`, because it can restore the CPU Torch lock.

## 4. Reproduce legacy data and construct the replay union

```bash
cd /workspace/hushmark-replay-training-0.2.0

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

The replay builder requires exactly the `synthetic-full` and `hushmark-dataset-prep-v1` sources,
rejects duplicate IDs and model-visible content overlap, and writes a digest-bound union manifest.
Training independently checks train/validation/locked-test isolation. The locked test files are
used only for overlap detection until final evaluation.

## 5. Run the 500-step hardware pilot

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/replay-train.jsonl \
  --validation-suite legacy=bench/train/outputs/synthetic-dev.jsonl \
  --validation-suite new=/workspace/hushmark-replay-data-0.2.0/data/new/validation.jsonl \
  --evaluation-suite new_locked=/workspace/hushmark-replay-data-0.2.0/data/new/test_locked.jsonl \
  --replay-source synthetic-full \
  --new-source hushmark-dataset-prep-v1 \
  --replay-ratio 0.70 \
  --output bench/train/outputs/a100-replay-pilot \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --max-steps 500 \
  --validation-every 100 \
  --checkpoint-every 100 \
  --keep-checkpoints 2

.venv/bin/python bench/train/check_pilot.py \
  --manifest bench/train/outputs/a100-replay-pilot/training_manifest.json
```

The checker exits non-zero unless the pilot reaches exactly 500 steps on an A100, uses mixed
precision, has finite losses, stays below the 80 GB safety boundary, remains adoption-ineligible,
and passes the combined legacy/new development gate. Do not start full training after a failed
pilot. Diagnose the pilot without consulting either locked test.

## 6. Run or resume full training

Only after the pilot checker returns `{"pass": true, ...}`:

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/replay-train.jsonl \
  --validation-suite legacy=bench/train/outputs/synthetic-dev.jsonl \
  --validation-suite new=/workspace/hushmark-replay-data-0.2.0/data/new/validation.jsonl \
  --evaluation-suite new_locked=/workspace/hushmark-replay-data-0.2.0/data/new/test_locked.jsonl \
  --replay-source synthetic-full \
  --new-source hushmark-dataset-prep-v1 \
  --replay-ratio 0.70 \
  --output bench/train/outputs/a100-replay-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --validation-every 100 \
  --early-stopping-patience 5 \
  --checkpoint-every 100 \
  --keep-checkpoints 2
```

If the process stops, repeat the identical command and append `--resume-from latest`. The run
fingerprint rejects changes to data, suite hashes, replay ratio, seed, hyperparameters, or hardware
mode. The completed manifest must contain `run_kind: full`, `complete: true`,
`development_gate_pass: true`, and `adoption_eligible: true`.

## 7. One-time legacy evaluation and artifact retrieval

Run the old locked benchmark exactly once against the development-selected full checkpoint:

```bash
.venv/bin/python bench/train/evaluate.py \
  --checkpoint bench/train/outputs/a100-replay-full \
  --report bench/train/outputs/a100-replay-full-legacy-verdict.json \
  --device cuda
```

Archive the candidate and evidence, generate its digest, then download both files:

```bash
cd /workspace/hushmark-replay-training-0.2.0
tar -czf /workspace/hushmark-replay-candidate.tar.gz \
  bench/train/outputs/a100-replay-full \
  bench/train/outputs/a100-replay-full-legacy-verdict.json \
  bench/train/outputs/a100-replay-pilot/training_manifest.json \
  bench/train/outputs/replay-train.manifest.json \
  bench/train/outputs/synthetic-dev.metadata.json \
  bench/train/outputs/synthetic-full.metadata.json
sha256sum /workspace/hushmark-replay-candidate.tar.gz \
  > /workspace/hushmark-replay-candidate.tar.gz.sha256
```

```bash
scp -i /tmp/hushmark-runpod-ssh/id_ed25519 -P RUNPOD_SSH_PORT \
  root@RUNPOD_PUBLIC_IP:/workspace/hushmark-replay-candidate.tar.gz \
  root@RUNPOD_PUBLIC_IP:/workspace/hushmark-replay-candidate.tar.gz.sha256 \
  dist/
```

Verify the outer archive and `training_manifest.json` weight digest locally before terminating the
Pod. Deleting a Pod also deletes its Pod Volume.

## 8. Final new-holdout comparison, locally

The incumbent `models/hushmark-tr` stays local. After extracting the candidate, compare both models
on the untouched 3,500-row new holdout with its data-bundle SHA-256:

```bash
NEW_TEST_SHA256=72a231bb7766d502d6d7db9c6d6851291f9d20041e7189a55722224922eb0d11

.venv/bin/python bench/train/evaluate_new_holdout.py \
  --candidate PATH_TO_EXTRACTED/a100-replay-full \
  --incumbent models/hushmark-tr \
  --dataset dataset-prep/prepared/v1/tasks/gliner_hushmark/evaluation/splits/test_locked.jsonl \
  --dataset-sha256 "$NEW_TEST_SHA256" \
  --legacy-report PATH_TO_EXTRACTED/a100-replay-full-legacy-verdict.json \
  --report PATH_TO_EXTRACTED/a100-replay-full-final-verdict.json \
  --device mps
```

Adoption requires both gates. The legacy gate requires at least +0.05 macro strict-F1 with no type
regression over 0.02. The new holdout applies the same rule to PERSON, ADDRESS, and DOB, and also
forbids any increase in false-positive spans across its 2,224 empty-gold examples. A failed result
is evidence, not permission to tune against either locked set.

## References

- [RunPod Pod storage and encrypted volumes](https://docs.runpod.io/pods/storage/types)
- [RunPod SSH connections](https://docs.runpod.io/pods/configuration/use-ssh)
- [RunPod Pod lifecycle](https://docs.runpod.io/pods/manage-pods)
- [RunPod Pod pricing](https://docs.runpod.io/pods/pricing)
