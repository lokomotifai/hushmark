# AC-1 RunPod execution runbook

This runbook executes only the separately authorized AC-1 model-training operation. It does not
publish artifacts, push a repository, or perform any AC-2 operation.

## Pod settings

Use a **Secure Cloud**, **On-Demand** Pod with one **A100 80 GB** GPU and the official RunPod
PyTorch template. Select a template with Python 3.12 support, enable full SSH, and attach a
100 GB Network Volume at `/workspace`. Network Volumes survive Pod deletion, but RunPod documents
that they are not encrypted. Put only the synthetic/public training inputs and model artifacts on
the volume; never put customer prompts, secrets, or production personal data there. Confirm the
live hourly price in the console before deployment.

The run is single-GPU. Do not select a multi-GPU Pod. On-Demand avoids interruption during the
first full run; checkpoint/resume is still enabled for operator error or Pod failure.

## 1. Build and verify the transfer artifact locally

From the repository root:

```bash
UV_CACHE_DIR=/tmp/hushmark-uv-cache uv run python scripts/build-training-bundle.py
shasum -a 256 dist/hushmark-ac1-training-0.1.0.tar.gz
```

The archive is generated from an explicit allowlist. It contains source, the locked public
benchmark, bootstrap code, and this runbook. It excludes the private research corpus, generated
training data, checkpoints, model weights, and all Git metadata.

Use the full SSH command shown by RunPod's **Connect** panel to transfer the archive. Full SSH is
required for SCP; replace the example host and port with the panel's values:

```bash
scp -P RUNPOD_SSH_PORT dist/hushmark-ac1-training-0.1.0.tar.gz \
  root@RUNPOD_PUBLIC_IP:/workspace/
```

## 2. Verify before executing bundled code

In the Pod terminal:

```bash
cd /workspace
tar -xzf hushmark-ac1-training-0.1.0.tar.gz
cd hushmark-ac1-training-0.1.0
python3 scripts/verify-training-bundle.py
```

Stop if verification does not report the number of verified allowlisted files.

## 3. Bootstrap the pinned CUDA environment

Install the pinned environment manager if `uv` is not already present, then run the CUDA-specific
bootstrap. This intentionally replaces the workspace's CPU-only Torch wheel with the official
PyTorch 2.13.0 CUDA 13.0 wheel and verifies the GPU before downloading the pinned GLiNER model.

```bash
python3 -m pip install --disable-pip-version-check uv==0.12.3
export PATH=/root/.local/bin:/usr/local/bin:/usr/bin:/bin
bash scripts/bootstrap-gpu.sh
bash scripts/bootstrap-gpu.sh --check
```

After bootstrap, always invoke `.venv/bin/python` directly. Running `uv run` can reconcile the
environment back to the CPU-only Torch wheel recorded for normal offline development.

## 4. Generate the isolated training corpus

The `full` synthesis profile skips the first 2,016 generator rows used by the locked evaluation
benchmark, then creates 200,592 new balanced rows. The preparation step labels their provenance as
`synthetic-full`. Training performs a second isolation check against evaluation IDs and
model-visible content.

```bash
.venv/bin/python bench/train/synthesize.py \
  --profile full \
  --seed 20260809 \
  --output bench/train/outputs/synthetic-full.jsonl

.venv/bin/python bench/train/prepare_gliner.py \
  --input bench/train/outputs/synthetic-full.jsonl \
  --source-format synthetic-full \
  --output bench/train/outputs/synthetic-full-gliner.jsonl
```

Retain both generated metadata and the printed SHA-256 values with the run evidence.

## 5. Run a bounded hardware pilot

The pilot uses the real full dataset and model but stops after 100 optimizer steps. Its manifest is
explicitly ineligible for adoption. It validates memory use, loss finiteness, CUDA mixed precision,
and checkpoint creation before the longer spend.

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --output bench/train/outputs/a100-pilot \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --max-steps 100 \
  --checkpoint-every 50 \
  --keep-checkpoints 2
```

Inspect `bench/train/outputs/a100-pilot/training_manifest.json`. Require `run_kind: pilot`,
`complete: false`, `adoption_eligible: false`, a finite loss, `hardware.gpu_name` containing A100,
and reasonable peak memory. If the pilot fails or exceeds memory, do not start the full run; lower
the batch size and create a new pilot output directory.

## 6. Run and, if needed, resume full training

Start the production candidate in a new directory:

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --output bench/train/outputs/a100-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --checkpoint-every 1000 \
  --keep-checkpoints 2
```

If the process or Pod stops, recreate the Pod with the same Network Volume and execute the exact
same command plus `--resume-from latest`. Do not change data, seed, epochs, batch size, learning
rate, device, or AMP mode; the run fingerprint rejects incompatible resumes.

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --output bench/train/outputs/a100-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --checkpoint-every 1000 \
  --keep-checkpoints 2 \
  --resume-from latest
```

The completed manifest must say `run_kind: full`, `complete: true`, and
`adoption_eligible: true` before evaluation.

## 7. Evaluate and retrieve evidence

Evaluate the completed checkpoint against all 2,016 locked rows:

```bash
.venv/bin/python bench/train/evaluate.py \
  --checkpoint bench/train/outputs/a100-full \
  --report bench/train/outputs/a100-full-verdict.json \
  --device cuda
```

The machine verdict adopts the model only if NER macro strict-F1 improves by at least 0.05 and no
NER type regresses by more than 0.02 strict-F1. A failed verdict is a valid experiment result; do
not change the incumbent registry.

Download these files before terminating the Pod:

- `a100-full/training_manifest.json`
- `a100-full/run_config.json`
- `a100-full/pytorch_model.bin` and all checkpoint configuration/tokenizer files
- `a100-full-verdict.json`
- `synthetic-full.metadata.json`

Verify the downloaded weight against `weights_sha256` in the training manifest. Keep the Network
Volume until the local copy and digest are confirmed; then delete the Pod to stop compute billing.

## Authoritative references checked for this runbook

- [RunPod Pod overview and official PyTorch template](https://docs.runpod.io/pods/overview)
- [RunPod Network Volumes](https://docs.runpod.io/storage/network-volumes)
- [RunPod SSH connection modes](https://docs.runpod.io/pods/configuration/use-ssh)
- [RunPod live GPU pricing](https://www.runpod.io/pricing)
- [Official PyTorch CUDA wheel matrix](https://pytorch.org/get-started/previous-versions/)
- [AI4Privacy OpenPII-1M dataset card](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m)
