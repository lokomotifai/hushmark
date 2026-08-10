# AC-1 RunPod execution runbook

This runbook executes only the separately authorized AC-1 model-training operation. It does not
publish artifacts, push a repository, or perform any AC-2 operation.

## Pod settings

Use a **Secure Cloud**, **On-Demand** Pod with one **A100 80 GB** GPU and the official RunPod
PyTorch template. Select a template with Python 3.12 support, enable full SSH, and attach either a
100 GB Network Volume or a 100 GB Pod Volume at `/workspace`. Network Volumes survive Pod deletion;
Pod Volumes are deleted with the Pod. RunPod documents that Network Volumes are not encrypted. Put
only the synthetic/public training inputs and model artifacts on either volume; never put customer
prompts, secrets, or production personal data there. Confirm the live hourly price in the console
before deployment.

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

Install the pinned environment manager in an isolated bootstrap virtual environment, then run the
CUDA-specific bootstrap. The isolated install works on PEP 668 externally-managed Python images
without changing the system interpreter. The CUDA bootstrap intentionally replaces the
workspace's CPU-only Torch wheel with the official PyTorch 2.13.0 CUDA 13.0 wheel and verifies the
GPU before downloading the pinned GLiNER model.

```bash
python3 -m venv /workspace/.uv-bootstrap
/workspace/.uv-bootstrap/bin/python -m pip install --disable-pip-version-check uv==0.12.3
export PATH=/workspace/.uv-bootstrap/bin:/usr/local/bin:/usr/bin:/bin
bash scripts/bootstrap-gpu.sh
bash scripts/bootstrap-gpu.sh --check
```

After bootstrap, always invoke `.venv/bin/python` directly. Running `uv run` can reconcile the
environment back to the CPU-only Torch wheel recorded for normal offline development.

## 4. Generate isolated development and training corpora

Reserve 1,008 development rows after the 2,016 locked final-evaluation rows. The `full` synthesis
profile then skips both reserved ranges before creating 200,592 training rows. Training performs a
second isolation check across all three sets using IDs and model-visible content. Development is
used for checkpoint selection; the locked benchmark remains untouched until the one final verdict.

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
```

Retain both generated metadata files and all printed SHA-256 values with the run evidence.

## 5. Run a bounded hardware pilot

The pilot uses the real full and development datasets but stops after 500 optimizer steps. Its
manifest is explicitly ineligible for adoption. It validates memory, loss, mixed precision,
balanced sampling, validation metrics, best-checkpoint selection, and early stopping before the
binding run.

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --validation-data bench/train/outputs/synthetic-dev.jsonl \
  --output bench/train/outputs/a100-pilot \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --max-steps 500 \
  --validation-every 100 \
  --checkpoint-every 100 \
  --keep-checkpoints 2
```

Inspect `bench/train/outputs/a100-pilot/training_manifest.json`. Require `run_kind: pilot`,
`complete: false`, `adoption_eligible: false`, a finite loss, `hardware.gpu_name` containing A100,
and reasonable peak memory. Also require development macro-F1 to improve without an over-limit
per-type regression before reusing the configuration. If it does not, create a new bounded pilot;
never tune against the locked benchmark.

## 6. Run and, if needed, resume full training

Start the production candidate in a new directory:

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --validation-data bench/train/outputs/synthetic-dev.jsonl \
  --output bench/train/outputs/a100-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --validation-every 100 \
  --early-stopping-patience 5 \
  --checkpoint-every 100 \
  --keep-checkpoints 2
```

If the process or Pod stops, recreate the Pod with the same Network Volume and execute the exact
same command plus `--resume-from latest`. Do not change data, development data, seed, epochs, batch
size, learning rates, sampling, validation cadence, device, or AMP mode; the run fingerprint
rejects incompatible resumes.

```bash
.venv/bin/python bench/train/train.py \
  --authorized-full-run \
  --data bench/train/outputs/synthetic-full-gliner.jsonl \
  --validation-data bench/train/outputs/synthetic-dev.jsonl \
  --output bench/train/outputs/a100-full \
  --device cuda \
  --amp auto \
  --epochs 3 \
  --batch-size 16 \
  --validation-every 100 \
  --early-stopping-patience 5 \
  --checkpoint-every 100 \
  --keep-checkpoints 2 \
  --resume-from latest
```

The completed manifest must say `run_kind: full`, `complete: true`,
`development_gate_pass: true`, and `adoption_eligible: true` before final evaluation. The selected
weights must come from `development_best_step`, not merely the last optimizer step.

## 7. Evaluate and retrieve evidence

Evaluate the completed checkpoint against all 2,016 locked rows:

```bash
.venv/bin/python bench/train/evaluate.py \
  --checkpoint bench/train/outputs/a100-full \
  --report bench/train/outputs/a100-full-verdict.json \
  --device cuda
```

The locked command is run exactly once for a development-selected candidate. The machine verdict
adopts the model only if NER macro strict-F1 improves by at least 0.05 and no NER type regresses by
more than 0.02 strict-F1. A failed verdict is a valid experiment result; do not tune against the
locked report or change the incumbent registry.

If and only if the locked verdict says `adopt: true`, export ONNX through the supported GLiNER
export API. Calibrate thresholds on development data only. First use one inference pass to compare
a threshold grid, then rerun the chosen fixed threshold over all development rows with batching:

```bash
.venv/bin/python bench/train/calibrate_onnx.py \
  --checkpoint bench/train/outputs/a100-full \
  --validation-data bench/train/outputs/synthetic-dev.jsonl \
  --onnx-model-file model.onnx \
  --threshold 0.1 --threshold 0.2 --threshold 0.275 --threshold 0.4 --threshold 0.5 \
  --report bench/train/outputs/a100-full/onnx-fp32-calibration.json

.venv/bin/python bench/train/calibrate_onnx.py \
  --checkpoint bench/train/outputs/a100-full \
  --validation-data bench/train/outputs/synthetic-dev.jsonl \
  --onnx-model-file model.onnx \
  --threshold <chosen-development-threshold> \
  --batch-size 8 \
  --report bench/train/outputs/a100-full/onnx-fp32-validation.json
```

Compare the full-development ONNX report with the Torch development-best report. Reject an export
if its macro strict-F1 loss or any per-type loss exceeds 0.02. Quantized and FP32 graphs are
separate candidates: a failed INT8 result must remain evidence-only and must never replace a
passing FP32 graph. Pin the adopted ONNX size, SHA-256, opset, and effective-threshold scale in
`core/models.yaml`, then verify the exact local artifact with `tools/export-onnx.py --verify-only`.

Download these files before terminating the Pod:

- `a100-full/training_manifest.json`
- `a100-full/run_config.json`
- `a100-full/pytorch_model.bin` and all checkpoint configuration/tokenizer files
- `a100-full-verdict.json`
- `a100-full/development-history.jsonl` and `development-best/validation_report.json`
- FP32/INT8 ONNX calibration and full-development validation reports, including rejected exports
- the adopted ONNX graph, its SHA-256, size, and export log
- `synthetic-dev.metadata.json`
- `synthetic-full.metadata.json`

Verify the downloaded weight against `weights_sha256` in the training manifest. Keep the attached
volume until the local copy and digest are confirmed; then stop and delete the Pod. With a Pod
Volume, deletion also destroys the remote evidence, so local archive and inner-weight digests must
both be verified first.

## Authoritative references checked for this runbook

- [RunPod Pod overview and official PyTorch template](https://docs.runpod.io/pods/overview)
- [RunPod Network Volumes](https://docs.runpod.io/storage/network-volumes)
- [RunPod SSH connection modes](https://docs.runpod.io/pods/configuration/use-ssh)
- [RunPod live GPU pricing](https://www.runpod.io/pricing)
- [Official PyTorch CUDA wheel matrix](https://pytorch.org/get-started/previous-versions/)
- [AI4Privacy OpenPII-1M dataset card](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m)
