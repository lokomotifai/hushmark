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
    adoption_verdict,
    assert_evaluation_isolation,
    json_lines,
    load_model_labels,
    load_prepared,
    load_validation_examples,
    prepare_record,
    resolve_training_max_width,
    sha256_file,
    smoke_records,
)
from hushmark_bench.training_state import (
    TrainingProgress,
    atomic_write_json,
    checkpoint_name,
    deterministic_balanced_epoch_indices,
    deterministic_epoch_indices,
    deterministic_replay_balanced_epoch_indices,
    linear_warmup_decay,
    normalized_progress,
    optimizer_parameter_groups,
    progress_dict,
    prune_checkpoints,
    resolve_resume_checkpoint,
    run_fingerprint,
    write_latest_checkpoint,
)
from hushmark_bench.validation import validate_ner_suites, validation_rank

ROOT = Path(__file__).resolve().parents[2]


def validation_suite_paths(args: argparse.Namespace) -> dict[str, Path]:
    suites: dict[str, Path] = {}
    if args.validation_data is not None:
        suites["development"] = args.validation_data
    for specification in getattr(args, "validation_suite", []):
        name, separator, raw_path = specification.partition("=")
        if not separator or not name or not raw_path or not name.replace("-", "_").isalnum():
            raise ValueError("validation suites must use NAME=PATH")
        if name in suites:
            raise ValueError(f"duplicate validation suite: {name}")
        suites[name] = Path(raw_path)
    return suites


def evaluation_suite_paths(args: argparse.Namespace) -> dict[str, Path]:
    suites = {"legacy_locked": args.evaluation_data}
    for specification in getattr(args, "evaluation_suite", []):
        name, separator, raw_path = specification.partition("=")
        if not separator or not name or not raw_path or not name.replace("-", "_").isalnum():
            raise ValueError("evaluation suites must use NAME=PATH")
        if name in suites:
            raise ValueError(f"duplicate evaluation suite: {name}")
        suites[name] = Path(raw_path)
    return suites


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


def save_development_best(
    *,
    model: Any,
    output: Path,
    report: dict[str, Any],
) -> Path:
    target = output / "development-best"
    temporary = output / ".development-best.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    model.save_pretrained(temporary / "model", safe_serialization=False)
    atomic_write_json(temporary / "validation_report.json", report)
    if target.exists():
        shutil.rmtree(target)
    temporary.replace(target)
    return target


def materialize_development_best(output: Path) -> None:
    source = output / "development-best/model"
    if not source.is_dir():
        raise FileNotFoundError("development-best model is missing")
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path, output / path.name)


def save_checkpoint(
    *,
    torch: Any,
    model: Any,
    optimizer: Any,
    scheduler: Any,
    scaler: Any,
    output: Path,
    fingerprint: str,
    progress: TrainingProgress,
    keep: int,
    validation_state: dict[str, Any] | None,
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
        "scheduler": scheduler.state_dict(),
        "scaler": scaler.state_dict(),
        "python_random_state": random.getstate(),
        "torch_random_state": torch.get_rng_state(),
        "cuda_random_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "progress": progress_dict(progress),
        "validation_state": validation_state,
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
    if args.validation_every < 1 or args.early_stopping_patience < 1:
        raise ValueError("validation cadence and early-stopping patience must be positive")
    if args.warmup_steps < 0:
        raise ValueError("warmup steps must not be negative")
    if args.validation_min_delta < 0 or not 0 <= args.validation_threshold <= 1:
        raise ValueError("validation delta or threshold is invalid")
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
    validation_suites: dict[str, list[dict[str, Any]]] = {}
    validation_records: list[dict[str, Any]] = []
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
        suite_paths = validation_suite_paths(args)
        if not suite_paths:
            raise ValueError("full training requires validation data")
        records = load_prepared(args.data)
        evaluation_paths = evaluation_suite_paths(args)
        evaluation_records_by_suite: dict[str, list[dict[str, Any]]] = {}
        for suite_name, suite_path in evaluation_paths.items():
            evaluation_records_by_suite[suite_name] = [
                prepare_record(example, labels, source=f"locked-evaluation-{suite_name}")
                for example in load_validation_examples(suite_path, labels)
            ]
        evaluation_records = [
            record
            for suite_records in evaluation_records_by_suite.values()
            for record in suite_records
        ]
        validation_records_by_suite: dict[str, list[dict[str, Any]]] = {}
        for suite_name, suite_path in suite_paths.items():
            examples = load_validation_examples(suite_path, labels)
            validation_suites[suite_name] = examples
            validation_records_by_suite[suite_name] = [
                prepare_record(example, labels, source=f"validation-{suite_name}")
                for example in examples
            ]
            validation_records.extend(validation_records_by_suite[suite_name])
        assert_evaluation_isolation(records, evaluation_records)
        assert_evaluation_isolation(validation_records, evaluation_records)
        suite_names = list(validation_records_by_suite)
        for index, suite_name in enumerate(suite_names):
            suite_records = validation_records_by_suite[suite_name]
            assert_evaluation_isolation(records, suite_records)
            for other_name in suite_names[index + 1 :]:
                assert_evaluation_isolation(suite_records, validation_records_by_suite[other_name])
        evaluation_names = list(evaluation_records_by_suite)
        for index, suite_name in enumerate(evaluation_names):
            suite_records = evaluation_records_by_suite[suite_name]
            for other_name in evaluation_names[index + 1 :]:
                assert_evaluation_isolation(suite_records, evaluation_records_by_suite[other_name])
        epochs = args.epochs
        batch_size = args.batch_size or 16
    if epochs < 1 or batch_size < 1:
        raise ValueError("epochs and batch size must be positive")

    width_records = [*records, *validation_records]
    effective_max_width, required_max_width = resolve_training_max_width(
        args.model_dir,
        width_records,
        requested=args.max_width,
    )

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
    encoder_learning_rate = (
        args.learning_rate if args.learning_rate is not None else args.encoder_learning_rate
    )
    head_learning_rate = (
        args.learning_rate if args.learning_rate is not None else args.head_learning_rate
    )
    expected_steps = math.ceil(len(records) / batch_size) * epochs
    suite_paths = validation_suite_paths(args) if not args.smoke else {}
    validation_manifest = {
        name: {
            "path": str(path),
            "sha256": sha256_file(path),
            "examples": len(validation_suites[name]),
        }
        for name, path in suite_paths.items()
    }
    evaluation_manifest = (
        {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "examples": len(evaluation_records_by_suite[name]),
            }
            for name, path in evaluation_paths.items()
        }
        if not args.smoke
        else {}
    )
    replay_values = (args.replay_source, args.new_source, args.replay_ratio)
    replay_enabled = any(value is not None for value in replay_values)
    if replay_enabled:
        if args.smoke or not all(value is not None for value in replay_values):
            raise ValueError("replay sampling requires both sources and a ratio on a full run")
        if not args.balanced_sampling:
            raise ValueError("replay sampling requires balanced sampling")
        if not 0.0 < args.replay_ratio < 1.0:
            raise ValueError("replay ratio must be between zero and one")
    replay_config = (
        {
            "replay_source": args.replay_source,
            "new_source": args.new_source,
            "replay_ratio": args.replay_ratio,
        }
        if replay_enabled
        else None
    )
    config = {
        "schema_version": 1,
        "base_model": "gliner_multi_pii-v1",
        "base_weights_sha256": sha256_file(args.model_dir / "pytorch_model.bin"),
        "training_records_sha256": records_sha256,
        "examples": len(records),
        "epochs": epochs,
        "batch_size": batch_size,
        "encoder_learning_rate": encoder_learning_rate,
        "head_learning_rate": head_learning_rate,
        "train_text_encoder": args.train_text_encoder and not args.smoke,
        "warmup_steps": args.warmup_steps,
        "balanced_sampling": args.balanced_sampling,
        "replay_sampling": replay_config,
        "max_width": effective_max_width,
        "required_gold_max_width": required_max_width,
        "validation_suites": validation_manifest,
        "evaluation_suites": evaluation_manifest,
        "validation_every": args.validation_every,
        "early_stopping_patience": args.early_stopping_patience,
        "validation_threshold": args.validation_threshold,
        "seed": args.seed,
        "device": device,
        "amp": amp_mode,
        "smoke": args.smoke,
    }
    fingerprint = run_fingerprint(config)
    model_source = resume_checkpoint / "model" if resume_checkpoint else args.model_dir
    model = GLiNER.from_pretrained(
        str(model_source),
        local_files_only=True,
        map_location="cpu",
        max_width=effective_max_width,
    )
    groups, parameters = optimizer_parameter_groups(
        model,
        train_text_encoder=args.train_text_encoder and not args.smoke,
        encoder_learning_rate=encoder_learning_rate,
        head_learning_rate=head_learning_rate,
    )
    model.to(device)
    model.train()
    collator = model._create_data_collator()
    optimizer = torch.optim.AdamW(groups, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lr_lambda=lambda step: linear_warmup_decay(
            step,
            warmup_steps=args.warmup_steps,
            total_steps=expected_steps,
        ),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=amp_mode == "fp16")
    progress = TrainingProgress(0, 0, 0, 0.0, 0, None)
    resumed_from: str | None = None
    validation_state: dict[str, Any] | None = None
    if resume_checkpoint is not None:
        checkpoint_manifest = json.loads(
            (resume_checkpoint / "checkpoint_manifest.json").read_text(encoding="utf-8")
        )
        if checkpoint_manifest.get("run_fingerprint") != fingerprint:
            raise ValueError("resume checkpoint does not match this run configuration")
        state = torch.load(resume_checkpoint / "state.pt", map_location="cpu", weights_only=True)
        optimizer.load_state_dict(state["optimizer"])
        optimizer_to_device(optimizer, device)
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        random.setstate(state["python_random_state"])
        torch.set_rng_state(state["torch_random_state"])
        if device == "cuda" and state["cuda_random_state"]:
            torch.cuda.set_rng_state_all(state["cuda_random_state"])
        progress = TrainingProgress(**state["progress"])
        validation_state = state.get("validation_state")
        if validation_suites and not isinstance(validation_state, dict):
            raise ValueError("resume checkpoint has no compatible validation state")
        resumed_from = str(resume_checkpoint)
        print(
            f"resuming step={progress.global_step} epoch={progress.epoch_index + 1} "
            f"offset={progress.next_sample_offset} from {resume_checkpoint}",
            flush=True,
        )

    args.output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output / "run_config.json", {**config, "run_fingerprint": fingerprint})
    history_path = args.output / "development-history.jsonl"
    if validation_suites and validation_state is None:
        model.eval()
        with torch.inference_mode():
            baseline = validate_ner_suites(
                model,
                validation_suites,
                labels,
                threshold=args.validation_threshold,
            )
        baseline_verdict = adoption_verdict(baseline, baseline, eligible=True)
        baseline_report = {
            "schema_version": 1,
            "step": 0,
            "candidate": baseline,
            "verdict": baseline_verdict,
        }
        baseline_rank = validation_rank(baseline_report)
        save_development_best(model=model, output=args.output, report=baseline_report)
        history_path.write_text(
            json.dumps(baseline_report, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validation_state = {
            "baseline": baseline,
            "best_report": baseline_report,
            "best_rank": list(baseline_rank),
            "best_step": 0,
            "validations_without_improvement": 0,
        }
        model.train()

    def validate_and_update(step: int) -> bool:
        nonlocal validation_state
        if not validation_suites or validation_state is None:
            return False
        model.eval()
        with torch.inference_mode():
            candidate = validate_ner_suites(
                model,
                validation_suites,
                labels,
                threshold=args.validation_threshold,
            )
        model.train()
        verdict = adoption_verdict(candidate, validation_state["baseline"], eligible=True)
        report = {
            "schema_version": 1,
            "step": step,
            "candidate": candidate,
            "verdict": verdict,
        }
        with history_path.open("a", encoding="utf-8") as history:
            history.write(json.dumps(report, sort_keys=True) + "\n")
        rank = validation_rank(report)
        best_rank = tuple(float(value) for value in validation_state["best_rank"])
        pass_transition = rank[0] > best_rank[0]
        macro_improvement = rank[1] >= best_rank[1] + args.validation_min_delta
        regression_improvement = rank[1] >= best_rank[1] and rank[2] > best_rank[2]
        improved = rank > best_rank and (
            pass_transition or macro_improvement or regression_improvement
        )
        if improved:
            save_development_best(model=model, output=args.output, report=report)
            validation_state.update(
                {
                    "best_report": report,
                    "best_rank": list(rank),
                    "best_step": step,
                    "validations_without_improvement": 0,
                }
            )
        else:
            validation_state["validations_without_improvement"] += 1
        print(
            f"development step={step} macro_f1={candidate['ner_macro_f1']:.6f} "
            f"technical_pass={str(verdict['technical_pass']).lower()} "
            f"best_step={validation_state['best_step']}",
            flush=True,
        )
        return validation_state["validations_without_improvement"] >= args.early_stopping_patience

    last_checkpoint_step = progress.global_step if resume_checkpoint is not None else 0
    stop_requested = args.max_steps is not None and progress.global_step >= args.max_steps
    stop_reason = "max-steps" if stop_requested else None

    try:
        for epoch_index in range(progress.epoch_index, epochs):
            if stop_requested:
                break
            offset = progress.next_sample_offset if epoch_index == progress.epoch_index else 0
            if replay_enabled:
                indices = deterministic_replay_balanced_epoch_indices(
                    records,
                    args.seed,
                    epoch_index,
                    replay_source=args.replay_source,
                    new_source=args.new_source,
                    replay_ratio=args.replay_ratio,
                )
            elif args.balanced_sampling and not args.smoke:
                indices = deterministic_balanced_epoch_indices(records, args.seed, epoch_index)
            else:
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
                scheduler.step()

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
                max_steps_reached = (
                    args.max_steps is not None and progress.global_step >= args.max_steps
                )
                validation_due = (
                    bool(validation_suites) and progress.global_step % args.validation_every == 0
                )
                early_stopping_reached = (
                    validate_and_update(progress.global_step) if validation_due else False
                )
                if max_steps_reached:
                    stop_reason = "max-steps"
                elif early_stopping_reached:
                    stop_reason = "early-stopping"
                stop_requested = max_steps_reached or early_stopping_reached
                should_checkpoint = (
                    progress.global_step % args.checkpoint_every == 0 or validation_due
                )
                if should_checkpoint or stop_requested:
                    save_checkpoint(
                        torch=torch,
                        model=model,
                        optimizer=optimizer,
                        scheduler=scheduler,
                        scaler=scaler,
                        output=args.output,
                        fingerprint=fingerprint,
                        progress=progress,
                        keep=args.keep_checkpoints,
                        validation_state=validation_state,
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
                scheduler=scheduler,
                scaler=scaler,
                output=args.output,
                fingerprint=fingerprint,
                progress=progress,
                keep=args.keep_checkpoints,
                validation_state=validation_state,
            )
        raise

    if progress.loss_count == 0 or progress.final_loss is None:
        raise RuntimeError("training completed no optimizer steps")
    if validation_suites and progress.global_step % args.validation_every:
        validate_and_update(progress.global_step)
    if stop_reason is None and progress.epoch_index >= epochs:
        stop_reason = "epochs-complete"
    complete = args.max_steps is None and stop_reason in {"epochs-complete", "early-stopping"}
    development_gate_pass = bool(
        validation_state and validation_state["best_report"]["verdict"]["technical_pass"]
    )
    if validation_suites:
        materialize_development_best(args.output)
    else:
        model.eval()
        model.save_pretrained(args.output, safe_serialization=False)
    elapsed = time.perf_counter() - started
    weights = args.output / "pytorch_model.bin"
    run_kind = "smoke" if args.smoke else ("full" if complete else "pilot")
    manifest = {
        "schema_version": 3,
        "model_id": "hushmark-tr-smoke" if args.smoke else "hushmark-tr",
        "base_model": "gliner_multi_pii-v1",
        "run_kind": run_kind,
        "smoke": args.smoke,
        "complete": complete,
        "adoption_eligible": not args.smoke and complete and development_gate_pass,
        "examples": len(records),
        "epochs": epochs,
        "batch_size": batch_size,
        "optimizer_steps": progress.global_step,
        "expected_optimizer_steps": expected_steps,
        "max_steps": args.max_steps,
        "stop_reason": stop_reason,
        "checkpoint_every": args.checkpoint_every,
        "kept_checkpoints": args.keep_checkpoints,
        "resumed_from": resumed_from,
        "seed": args.seed,
        "amp": amp_mode,
        "frozen_components": [] if args.train_text_encoder and not args.smoke else ["text_encoder"],
        "encoder_learning_rate": encoder_learning_rate,
        "head_learning_rate": head_learning_rate,
        "warmup_steps": args.warmup_steps,
        "balanced_sampling": args.balanced_sampling,
        "replay_sampling": replay_config,
        "max_width": effective_max_width,
        "required_gold_max_width": required_max_width,
        "mean_loss": progress.loss_sum / progress.loss_count,
        "final_loss": progress.final_loss,
        "elapsed_seconds": elapsed,
        "weights_sha256": sha256_file(weights),
        "training_records_sha256": records_sha256,
        "validation_suites": validation_manifest,
        "evaluation_suites": evaluation_manifest,
        "development_gate_pass": development_gate_pass,
        "development_best_step": validation_state["best_step"] if validation_state else None,
        "development_best_report": (validation_state["best_report"] if validation_state else None),
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
    parser.add_argument("--validation-data", type=Path)
    parser.add_argument(
        "--validation-suite",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="named validation suite; may be repeated instead of --validation-data",
    )
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/gliner_multi_pii-v1")
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument(
        "--evaluation-data", type=Path, default=ROOT / "bench/data/hushmark-bench-v0.jsonl"
    )
    parser.add_argument(
        "--evaluation-suite",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="additional locked evaluation suite used only for overlap checks; may be repeated",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resume-from", type=Path, help="checkpoint path or the literal 'latest'")
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument(
        "--learning-rate",
        type=float,
        help="legacy override that applies one rate to both encoder and head",
    )
    parser.add_argument("--encoder-learning-rate", type=float, default=5e-6)
    parser.add_argument("--head-learning-rate", type=float, default=1e-5)
    parser.add_argument("--train-text-encoder", action="store_true")
    parser.add_argument("--warmup-steps", type=int, default=50)
    parser.add_argument("--validation-every", type=int, default=100)
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument("--validation-min-delta", type=float, default=0.002)
    parser.add_argument("--validation-threshold", type=float, default=0.55)
    parser.add_argument(
        "--max-width",
        type=int,
        help="GLiNER candidate width; defaults to the widest gold span or the base model width",
    )
    parser.add_argument(
        "--balanced-sampling",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--replay-source")
    parser.add_argument("--new-source")
    parser.add_argument("--replay-ratio", type=float)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cuda")
    parser.add_argument("--amp", choices=("auto", "off", "bf16", "fp16"), default="auto")
    parser.add_argument("--max-steps", type=int, help="bounded pilot; never adoption-eligible")
    parser.add_argument("--checkpoint-every", type=int, default=100)
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
