#!/usr/bin/env python3
"""Fine-tune the pinned GLiNER model with isolation and recoverable checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hushmark_bench.training import (
    assert_evaluation_isolation,
    json_lines,
    load_model_labels,
    load_prepared,
    prepare_hushmark_records,
    sha256_file,
    smoke_records,
)
from hushmark_bench.training_state import (
    TrainingProgress,
    atomic_write_json,
    checkpoint_name,
    deterministic_epoch_indices,
    normalized_progress,
    progress_dict,
    prune_checkpoints,
    resolve_resume_checkpoint,
    run_fingerprint,
    write_latest_checkpoint,
)

ROOT = Path(__file__).resolve().parents[2]


def optimizer_to_device(optimizer: Any, device: str) -> None:
    for state in optimizer.state.values():
        for key, value in state.items():
            if hasattr(value, "to"):
                state[key] = value.to(device)


def resolve_amp_mode(torch: Any, device: str, requested: str) -> str:
    if device != "cuda":
        if requested not in {"auto", "off"}:
            raise ValueError("mixed precision is supported only on CUDA")
        return "off"
    if requested == "auto":
        return "bf16" if torch.cuda.is_bf16_supported() else "fp16"
    return requested


def hardware_manifest(torch: Any, device: str) -> dict[str, Any]:
    hardware: dict[str, Any] = {
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "device": device,
    }
    if device == "cuda":
        hardware.update(
            {
                "gpu_count": torch.cuda.device_count(),
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_capability": list(torch.cuda.get_device_capability(0)),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(0),
            }
        )
    return hardware


def save_checkpoint(
    *,
    torch: Any,
    model: Any,
    optimizer: Any,
    scaler: Any,
    output: Path,
    fingerprint: str,
    progress: TrainingProgress,
    keep: int,
) -> Path:
    checkpoints_dir = output / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    name = checkpoint_name(progress.global_step)
    target = checkpoints_dir / name
    temporary = checkpoints_dir / f".{name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    if target.exists():
        raise FileExistsError(f"checkpoint already exists: {target}")
    temporary.mkdir()
    model.save_pretrained(temporary / "model", safe_serialization=False)
    state = {
        "optimizer": optimizer.state_dict(),
        "scaler": scaler.state_dict(),
        "python_random_state": random.getstate(),
        "torch_random_state": torch.get_rng_state(),
        "cuda_random_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "progress": progress_dict(progress),
    }
    torch.save(state, temporary / "state.pt")
    atomic_write_json(
        temporary / "checkpoint_manifest.json",
        {
            "schema_version": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "run_fingerprint": fingerprint,
            "progress": progress_dict(progress),
        },
    )
    temporary.replace(target)
    write_latest_checkpoint(output, target)
    removed = prune_checkpoints(checkpoints_dir, keep)
    for path in removed:
        print(f"pruned checkpoint {path}", flush=True)
    print(f"saved checkpoint {target}", flush=True)
    return target


def train(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import torch
    from gliner import GLiNER
    from torch.utils.data import DataLoader, Subset

    started = time.perf_counter()
    if args.checkpoint_every < 1 or args.keep_checkpoints < 1:
        raise ValueError("checkpoint cadence and retention must be positive")
    if args.max_steps is not None and args.max_steps < 1:
        raise ValueError("max steps must be positive")
    device = "cpu" if args.smoke else args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS was requested but is unavailable")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True

    labels = load_model_labels(args.registry)
    if args.smoke:
        records = (
            smoke_records(args.seed, labels) if args.data is None else load_prepared(args.data)
        )
        if len(records) < 200:
            raise ValueError("smoke training requires at least 200 prepared examples")
        records = random.Random(args.seed).sample(records, 200)
        epochs = 1
        batch_size = args.batch_size or 8
    else:
        if not args.authorized_full_run:
            raise PermissionError(
                "full training requires --authorized-full-run after AC-1 approval"
            )
        if args.data is None:
            raise ValueError("full training requires --data")
        records = load_prepared(args.data)
        evaluation_records = prepare_hushmark_records(args.evaluation_data, labels)
        assert_evaluation_isolation(records, evaluation_records)
        epochs = args.epochs
        batch_size = args.batch_size or 16
    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch size must be positive")

    resume_checkpoint = resolve_resume_checkpoint(args.output, args.resume_from)
    if args.output.exists() and resume_checkpoint is None:
        raise FileExistsError(f"output already exists: {args.output}")
    if not args.output.exists() and resume_checkpoint is not None:
        raise FileNotFoundError(f"resume output is missing: {args.output}")
    if not (args.model_dir / "pytorch_model.bin").is_file():
        raise FileNotFoundError(f"pinned base model is missing: {args.model_dir}")

    amp_mode = resolve_amp_mode(torch, device, args.amp)
    records_sha256 = (
        sha256_file(args.data)
        if args.data is not None
        else hashlib.sha256(json_lines(records).encode()).hexdigest()
    )
    config = {
        "schema_version": 1,
        "base_model": "gliner_multi_pii-v1",
        "base_weights_sha256": sha256_file(args.model_dir / "pytorch_model.bin"),
        "training_records_sha256": records_sha256,
        "examples": len(records),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": args.learning_rate,
        "seed": args.seed,
        "device": device,
        "amp": amp_mode,
        "smoke": args.smoke,
    }
    fingerprint = run_fingerprint(config)
    model_source = resume_checkpoint / "model" if resume_checkpoint else args.model_dir
    model = GLiNER.from_pretrained(str(model_source), local_files_only=True, map_location="cpu")
    model.to(device)
    if args.smoke:
        model.freeze_component("text_encoder")
    model.train()
    collator = model._create_data_collator()
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not parameters:
        raise RuntimeError("training configuration has no trainable parameters")
    optimizer = torch.optim.AdamW(parameters, lr=args.learning_rate, weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=amp_mode == "fp16")
    progress = TrainingProgress(0, 0, 0, 0.0, 0, None)
    resumed_from: str | None = None
    if resume_checkpoint is not None:
        checkpoint_manifest = json.loads(
            (resume_checkpoint / "checkpoint_manifest.json").read_text(encoding="utf-8")
        )
        if checkpoint_manifest.get("run_fingerprint") != fingerprint:
            raise ValueError("resume checkpoint does not match this run configuration")
        state = torch.load(resume_checkpoint / "state.pt", map_location="cpu", weights_only=False)
        optimizer.load_state_dict(state["optimizer"])
        optimizer_to_device(optimizer, device)
        scaler.load_state_dict(state["scaler"])
        random.setstate(state["python_random_state"])
        torch.set_rng_state(state["torch_random_state"])
        if device == "cuda" and state["cuda_random_state"]:
            torch.cuda.set_rng_state_all(state["cuda_random_state"])
        progress = TrainingProgress(**state["progress"])
        resumed_from = str(resume_checkpoint)
        print(
            f"resuming step={progress.global_step} epoch={progress.epoch_index + 1} "
            f"offset={progress.next_sample_offset} from {resume_checkpoint}",
            flush=True,
        )

    args.output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output / "run_config.json", {**config, "run_fingerprint": fingerprint})
    expected_steps = math.ceil(len(records) / batch_size) * epochs
    last_checkpoint_step = progress.global_step if resume_checkpoint is not None else 0
    stop_requested = args.max_steps is not None and progress.global_step >= args.max_steps

    try:
        for epoch_index in range(progress.epoch_index, epochs):
            if stop_requested:
                break
            offset = progress.next_sample_offset if epoch_index == progress.epoch_index else 0
            indices = deterministic_epoch_indices(len(records), args.seed, epoch_index)
            remaining = Subset(records, indices[offset:])
            loader = DataLoader(
                remaining,
                batch_size=batch_size,
                shuffle=False,
                collate_fn=collator,
                num_workers=0,
                pin_memory=device == "cuda",
            )
            for batch in loader:
                batch = {
                    key: value.to(device, non_blocking=device == "cuda")
                    if isinstance(value, torch.Tensor)
                    else value
                    for key, value in batch.items()
                }
                optimizer.zero_grad(set_to_none=True)
                amp_dtype = torch.bfloat16 if amp_mode == "bf16" else torch.float16
                with torch.autocast(device_type="cuda", dtype=amp_dtype, enabled=amp_mode != "off"):
                    output = model(**batch, reduction="mean", masking="none")
                if output.loss is None or not torch.isfinite(output.loss):
                    raise RuntimeError("GLiNER returned a missing or non-finite loss")
                if scaler.is_enabled():
                    scaler.scale(output.loss).backward()
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(parameters, 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    output.loss.backward()
                    torch.nn.utils.clip_grad_norm_(parameters, 1.0)
                    optimizer.step()

                loss = float(output.loss.detach())
                next_offset = min(len(records), offset + batch_size)
                progress = normalized_progress(
                    epoch_index=epoch_index,
                    next_sample_offset=next_offset,
                    global_step=progress.global_step + 1,
                    loss_sum=progress.loss_sum + loss,
                    loss_count=progress.loss_count + 1,
                    final_loss=loss,
                    examples=len(records),
                )
                offset = next_offset
                print(
                    f"step={progress.global_step}/{expected_steps} "
                    f"epoch={epoch_index + 1}/{epochs} loss={loss:.6f}",
                    flush=True,
                )
                stop_requested = (
                    args.max_steps is not None and progress.global_step >= args.max_steps
                )
                should_checkpoint = progress.global_step % args.checkpoint_every == 0
                if should_checkpoint or stop_requested:
                    save_checkpoint(
                        torch=torch,
                        model=model,
                        optimizer=optimizer,
                        scaler=scaler,
                        output=args.output,
                        fingerprint=fingerprint,
                        progress=progress,
                        keep=args.keep_checkpoints,
                    )
                    last_checkpoint_step = progress.global_step
                if stop_requested:
                    break
    except KeyboardInterrupt:
        if progress.global_step > 0 and progress.global_step != last_checkpoint_step:
            save_checkpoint(
                torch=torch,
                model=model,
                optimizer=optimizer,
                scaler=scaler,
                output=args.output,
                fingerprint=fingerprint,
                progress=progress,
                keep=args.keep_checkpoints,
            )
        raise

    if progress.loss_count == 0 or progress.final_loss is None:
        raise RuntimeError("training completed no optimizer steps")
    complete = progress.epoch_index >= epochs
    model.eval()
    model.save_pretrained(args.output, safe_serialization=False)
    elapsed = time.perf_counter() - started
    weights = args.output / "pytorch_model.bin"
    run_kind = "smoke" if args.smoke else ("full" if complete else "pilot")
    manifest = {
        "schema_version": 2,
        "model_id": "hushmark-tr-smoke" if args.smoke else "hushmark-tr",
        "base_model": "gliner_multi_pii-v1",
        "run_kind": run_kind,
        "smoke": args.smoke,
        "complete": complete,
        "adoption_eligible": not args.smoke and complete,
        "examples": len(records),
        "epochs": epochs,
        "batch_size": batch_size,
        "optimizer_steps": progress.global_step,
        "expected_optimizer_steps": expected_steps,
        "max_steps": args.max_steps,
        "checkpoint_every": args.checkpoint_every,
        "kept_checkpoints": args.keep_checkpoints,
        "resumed_from": resumed_from,
        "seed": args.seed,
        "amp": amp_mode,
        "frozen_components": ["text_encoder"] if args.smoke else [],
        "learning_rate": args.learning_rate,
        "mean_loss": progress.loss_sum / progress.loss_count,
        "final_loss": progress.final_loss,
        "elapsed_seconds": elapsed,
        "weights_sha256": sha256_file(weights),
        "training_records_sha256": records_sha256,
        "training_sources": sorted({str(record.get("source", "unknown")) for record in records}),
        "run_fingerprint": fingerprint,
        "hardware": hardware_manifest(torch, device),
    }
    atomic_write_json(args.output / "training_manifest.json", manifest)
    if args.smoke and elapsed >= 600:
        raise RuntimeError(f"CPU smoke training exceeded 10 minutes: {elapsed:.1f}s")
    print(json.dumps(manifest, sort_keys=True))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--authorized-full-run", action="store_true")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/gliner_multi_pii-v1")
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument(
        "--evaluation-data", type=Path, default=ROOT / "bench/data/hushmark-bench-v0.jsonl"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume-from", type=Path, help="checkpoint path or the literal 'latest'")
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cuda")
    parser.add_argument("--amp", choices=("auto", "off", "bf16", "fp16"), default="auto")
    parser.add_argument("--max-steps", type=int, help="bounded pilot; never adoption-eligible")
    parser.add_argument("--checkpoint-every", type=int, default=1000)
    parser.add_argument("--keep-checkpoints", type=int, default=2)
    args = parser.parse_args()
    if not args.smoke and not args.authorized_full_run:
        parser.error("choose --smoke or provide --authorized-full-run after AC-1 approval")
    if args.output is None:
        args.output = ROOT / (
            "bench/train/outputs/smoke-checkpoint"
            if args.smoke
            else "bench/train/outputs/full-checkpoint"
        )
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
