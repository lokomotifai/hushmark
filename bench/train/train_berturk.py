#!/usr/bin/env python3
"""Train the pinned BERTurk encoder with Hushmark's fixed span-NER head."""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hushmark_bench.berturk_span import BerturkSpanModel
from hushmark_bench.training import (
    NER_TYPES,
    assert_evaluation_isolation,
    load_model_labels,
    load_prepared,
    load_validation_examples,
    prepare_record,
    prepared_required_max_width,
    sha256_file,
)
from hushmark_bench.training_state import (
    TrainingProgress,
    atomic_write_json,
    checkpoint_name,
    deterministic_replay_balanced_epoch_indices,
    linear_warmup_decay,
    normalized_progress,
    progress_dict,
    prune_checkpoints,
    resolve_resume_checkpoint,
    run_fingerprint,
    write_latest_checkpoint,
)
from hushmark_bench.validation import combine_validation_reports, validate_ner_model_batched

ROOT = Path(__file__).resolve().parents[2]
BASE_MODEL_ID = "dbmdz/bert-base-turkish-cased"
BASE_MODEL_REVISION = "b6e1de16c983e0f2c70664591ea3f22810072608"


def named_paths(specifications: Sequence[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for specification in specifications:
        name, separator, raw_path = specification.partition("=")
        normalized_name = name.replace("-", "").replace("_", "")
        if not separator or not name or not raw_path or not normalized_name.isalnum():
            raise ValueError("suite paths must use NAME=PATH")
        if name in paths:
            raise ValueError(f"duplicate suite: {name}")
        paths[name] = Path(raw_path)
    return paths


def resolve_amp_mode(torch: Any, device: str, requested: str) -> str:
    if device != "cuda":
        if requested not in {"auto", "off"}:
            raise ValueError("mixed precision is supported only on CUDA")
        return "off"
    if requested == "auto":
        return "bf16" if torch.cuda.is_bf16_supported() else "fp16"
    return requested


def hardware_manifest(torch: Any, device: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "device": device,
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
    }
    if device == "cuda":
        result.update(
            {
                "gpu_count": torch.cuda.device_count(),
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_capability": list(torch.cuda.get_device_capability(0)),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(0),
            }
        )
    return result


def validate_suites(
    model: BerturkSpanModel,
    suites: Mapping[str, Sequence[Mapping[str, Any]]],
    labels: Mapping[str, str],
    *,
    threshold: float,
    batch_size: int,
) -> dict[str, Any]:
    reports = {
        name: validate_ner_model_batched(
            model,
            examples,
            labels,
            threshold=threshold,
            batch_size=batch_size,
        )
        for name, examples in suites.items()
    }
    return combine_validation_reports(reports, threshold=threshold)


def report_rank(report: Mapping[str, Any]) -> tuple[float, float]:
    candidate = report.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ValueError("development report has no candidate metrics")
    false_positives = 0
    suites = candidate.get("suites")
    if isinstance(suites, Mapping):
        for suite in suites.values():
            if isinstance(suite, Mapping):
                empty = suite.get("empty_gold")
                if isinstance(empty, Mapping):
                    false_positives += int(empty.get("false_positive_spans", 0))
    return float(candidate["ner_macro_f1"]), -float(false_positives)


def save_checkpoint(
    *,
    torch: Any,
    model: BerturkSpanModel,
    optimizer: Any,
    scheduler: Any,
    scaler: Any,
    output: Path,
    fingerprint: str,
    progress: TrainingProgress,
    keep: int,
    development_state: Mapping[str, Any] | None,
) -> Path:
    checkpoints = output / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    name = checkpoint_name(progress.global_step)
    target = checkpoints / name
    temporary = checkpoints / f".{name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    if target.exists():
        raise FileExistsError(f"checkpoint already exists: {target}")
    temporary.mkdir()
    model.save_artifact(temporary / "model")
    torch.save(
        {
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "scaler": scaler.state_dict(),
            "python_random_state": random.getstate(),
            "torch_random_state": torch.get_rng_state(),
            "cuda_random_state": torch.cuda.get_rng_state_all()
            if torch.cuda.is_available()
            else [],
            "progress": progress_dict(progress),
            "development_state": dict(development_state) if development_state else None,
        },
        temporary / "state.pt",
    )
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
    for removed in prune_checkpoints(checkpoints, keep):
        print(f"pruned checkpoint {removed}", flush=True)
    print(f"saved checkpoint {target}", flush=True)
    return target


def save_development_best(
    model: BerturkSpanModel,
    output: Path,
    report: Mapping[str, Any],
) -> None:
    temporary = output / ".development-best.tmp"
    target = output / "development-best"
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    model.save_artifact(temporary / "model")
    atomic_write_json(temporary / "validation_report.json", report)
    if target.exists():
        shutil.rmtree(target)
    temporary.replace(target)


def optimizer_to_device(optimizer: Any, device: str) -> None:
    for state in optimizer.state.values():
        for key, value in state.items():
            if hasattr(value, "to"):
                state[key] = value.to(device)


def train(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader, Subset
    from transformers import AutoModel, AutoTokenizer

    started = time.perf_counter()
    if not args.authorized_full_run:
        raise PermissionError("BERTurk GPU training requires --authorized-full-run")
    if args.max_steps is not None and args.max_steps < 1:
        raise ValueError("max steps must be positive")
    if min(args.epochs, args.batch_size, args.validation_every, args.checkpoint_every) < 1:
        raise ValueError("training counts must be positive")
    if not 0.0 < args.replay_ratio < 1.0:
        raise ValueError("replay ratio must be between zero and one")
    if not 0.0 <= args.validation_threshold <= 1.0:
        raise ValueError("validation threshold must be between zero and one")
    if args.max_length < 8 or args.max_width < 1:
        raise ValueError("sequence length or span width is invalid")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True

    labels = load_model_labels(args.registry)
    label_names = [labels[entity_type] for entity_type in NER_TYPES]
    records = load_prepared(args.data)
    validation_paths = named_paths(args.validation_suite)
    evaluation_paths = named_paths(args.evaluation_suite)
    if not validation_paths or not evaluation_paths:
        raise ValueError("training requires named validation and locked evaluation suites")
    validation_suites: dict[str, list[dict[str, Any]]] = {}
    validation_prepared: dict[str, list[dict[str, Any]]] = {}
    evaluation_prepared: dict[str, list[dict[str, Any]]] = {}
    for name, path in validation_paths.items():
        examples = load_validation_examples(path, labels)
        validation_suites[name] = examples
        validation_prepared[name] = [
            prepare_record(example, labels, source=f"validation-{name}") for example in examples
        ]
    for name, path in evaluation_paths.items():
        evaluation_prepared[name] = [
            prepare_record(example, labels, source=f"locked-evaluation-{name}")
            for example in load_validation_examples(path, labels)
        ]
    all_evaluation = [row for rows in evaluation_prepared.values() for row in rows]
    assert_evaluation_isolation(records, all_evaluation)
    for rows in validation_prepared.values():
        assert_evaluation_isolation(records, rows)
        assert_evaluation_isolation(rows, all_evaluation)
    validation_names = list(validation_prepared)
    for index, name in enumerate(validation_names):
        for other in validation_names[index + 1 :]:
            assert_evaluation_isolation(validation_prepared[name], validation_prepared[other])
    evaluation_names = list(evaluation_prepared)
    for index, name in enumerate(evaluation_names):
        for other in evaluation_names[index + 1 :]:
            assert_evaluation_isolation(evaluation_prepared[name], evaluation_prepared[other])

    required_max_width = prepared_required_max_width(
        [*records, *(row for rows in validation_prepared.values() for row in rows)]
    )
    if args.max_width < required_max_width:
        raise ValueError(
            f"max_width={args.max_width} cannot represent gold width={required_max_width}"
        )
    resume_checkpoint = resolve_resume_checkpoint(args.output, args.resume_from)
    if args.output.exists() and resume_checkpoint is None:
        raise FileExistsError(f"output already exists: {args.output}")
    if not args.model_dir.is_dir() and resume_checkpoint is None:
        raise FileNotFoundError(f"pinned BERTurk snapshot is missing: {args.model_dir}")

    amp_mode = resolve_amp_mode(torch, args.device, args.amp)
    expected_steps = math.ceil(len(records) / args.batch_size) * args.epochs
    base_weights = args.model_dir / "model.safetensors"
    config = {
        "schema_version": 1,
        "architecture": "berturk-fixed-span-ner",
        "base_model": BASE_MODEL_ID,
        "base_revision": args.base_revision,
        "base_weights_sha256": sha256_file(base_weights) if base_weights.is_file() else None,
        "training_records_sha256": sha256_file(args.data),
        "examples": len(records),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "encoder_learning_rate": args.encoder_learning_rate,
        "head_learning_rate": args.head_learning_rate,
        "warmup_steps": args.warmup_steps,
        "max_length": args.max_length,
        "max_width": args.max_width,
        "required_gold_max_width": required_max_width,
        "negative_ratio": args.negative_ratio,
        "minimum_negatives": args.minimum_negatives,
        "replay_source": args.replay_source,
        "new_source": args.new_source,
        "replay_ratio": args.replay_ratio,
        "validation_suites": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in validation_paths.items()
        },
        "evaluation_suites": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in evaluation_paths.items()
        },
        "validation_every": args.validation_every,
        "validation_threshold": args.validation_threshold,
        "device": args.device,
        "amp": amp_mode,
        "seed": args.seed,
    }
    fingerprint = run_fingerprint(config)
    if resume_checkpoint is None:
        encoder = AutoModel.from_pretrained(
            args.model_dir, local_files_only=True, use_safetensors=True
        )
        tokenizer = AutoTokenizer.from_pretrained(
            args.model_dir, local_files_only=True, use_fast=True
        )
        model = BerturkSpanModel(
            encoder,
            tokenizer,
            label_names,
            max_length=args.max_length,
            max_width=args.max_width,
        )
    else:
        model = BerturkSpanModel.load_artifact(resume_checkpoint / "model")

    encoder_parameters = list(model.encoder.parameters())
    head_parameters = [
        parameter for name, parameter in model.named_parameters() if not name.startswith("encoder.")
    ]
    optimizer = torch.optim.AdamW(
        [
            {
                "params": encoder_parameters,
                "lr": args.encoder_learning_rate,
                "group_name": "encoder",
            },
            {
                "params": head_parameters,
                "lr": args.head_learning_rate,
                "group_name": "span_head",
            },
        ],
        weight_decay=0.01,
    )
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lr_lambda=lambda step: linear_warmup_decay(
            step, warmup_steps=args.warmup_steps, total_steps=expected_steps
        ),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=amp_mode == "fp16")
    progress = TrainingProgress(0, 0, 0, 0.0, 0, None)
    development_state: dict[str, Any] | None = None
    resumed_from: str | None = None
    if resume_checkpoint is not None:
        checkpoint_manifest = json.loads(
            (resume_checkpoint / "checkpoint_manifest.json").read_text(encoding="utf-8")
        )
        if checkpoint_manifest.get("run_fingerprint") != fingerprint:
            raise ValueError("resume checkpoint does not match the run configuration")
        state = torch.load(resume_checkpoint / "state.pt", map_location="cpu", weights_only=True)
        optimizer.load_state_dict(state["optimizer"])
        scheduler.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        random.setstate(state["python_random_state"])
        torch.set_rng_state(state["torch_random_state"])
        if args.device == "cuda" and state["cuda_random_state"]:
            torch.cuda.set_rng_state_all(state["cuda_random_state"])
        progress = TrainingProgress(**state["progress"])
        development_state = state.get("development_state")
        resumed_from = str(resume_checkpoint)

    model.to(args.device)
    optimizer_to_device(optimizer, args.device)
    model.train()
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output / "run_config.json", {**config, "run_fingerprint": fingerprint})
    history_path = args.output / "development-history.jsonl"
    collator = model.make_collator(training=True, seed=args.seed)
    collator.negative_ratio = args.negative_ratio
    collator.minimum_negatives = args.minimum_negatives

    def validate_and_update(step: int) -> bool:
        nonlocal development_state
        report = {
            "schema_version": 1,
            "step": step,
            "candidate": validate_suites(
                model,
                validation_suites,
                labels,
                threshold=args.validation_threshold,
                batch_size=args.validation_batch_size,
            ),
        }
        rank = report_rank(report)
        with history_path.open("a", encoding="utf-8") as history:
            history.write(json.dumps(report, sort_keys=True) + "\n")
        best_rank = (
            tuple(float(value) for value in development_state["best_rank"])
            if development_state
            else (-1.0, -math.inf)
        )
        improved = rank > best_rank and (
            development_state is None or rank[0] >= best_rank[0] + args.validation_min_delta
        )
        if improved:
            save_development_best(model, args.output, report)
            development_state = {
                "best_report": report,
                "best_rank": list(rank),
                "best_step": step,
                "validations_without_improvement": 0,
            }
        elif development_state is not None:
            development_state["validations_without_improvement"] += 1
        print(
            f"development step={step} macro_f1={rank[0]:.6f} "
            f"best_step={development_state['best_step'] if development_state else 'none'}",
            flush=True,
        )
        return bool(
            development_state
            and development_state["validations_without_improvement"] >= args.early_stopping_patience
        )

    stop_requested = args.max_steps is not None and progress.global_step >= args.max_steps
    stop_reason = "max-steps" if stop_requested else None
    last_checkpoint_step = progress.global_step if resume_checkpoint else 0
    for epoch_index in range(progress.epoch_index, args.epochs):
        if stop_requested:
            break
        offset = progress.next_sample_offset if epoch_index == progress.epoch_index else 0
        indices = deterministic_replay_balanced_epoch_indices(
            records,
            args.seed,
            epoch_index,
            replay_source=args.replay_source,
            new_source=args.new_source,
            replay_ratio=args.replay_ratio,
        )
        loader = DataLoader(
            Subset(records, indices[offset:]),
            batch_size=args.batch_size,
            shuffle=False,
            collate_fn=collator,
            num_workers=0,
            pin_memory=args.device == "cuda",
        )
        for batch in loader:
            batch = {
                key: value.to(args.device, non_blocking=args.device == "cuda")
                for key, value in batch.items()
            }
            optimizer.zero_grad(set_to_none=True)
            amp_dtype = torch.bfloat16 if amp_mode == "bf16" else torch.float16
            with torch.autocast(device_type="cuda", dtype=amp_dtype, enabled=amp_mode != "off"):
                output = model(**batch)
            loss = output.get("loss")
            if loss is None or not torch.isfinite(loss):
                raise RuntimeError("BERTurk span model returned a missing or non-finite loss")
            if scaler.is_enabled():
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            scheduler.step()
            batch_examples = int(batch["input_ids"].shape[0])
            loss_value = float(loss.detach())
            offset = min(len(records), offset + batch_examples)
            progress = normalized_progress(
                epoch_index=epoch_index,
                next_sample_offset=offset,
                global_step=progress.global_step + 1,
                loss_sum=progress.loss_sum + loss_value,
                loss_count=progress.loss_count + 1,
                final_loss=loss_value,
                examples=len(records),
            )
            if progress.global_step == 1 or progress.global_step % 20 == 0:
                print(
                    f"step={progress.global_step}/{expected_steps} "
                    f"epoch={epoch_index + 1}/{args.epochs} loss={loss_value:.6f}",
                    flush=True,
                )
            validation_due = progress.global_step % args.validation_every == 0
            early_stop = validate_and_update(progress.global_step) if validation_due else False
            max_steps_reached = (
                args.max_steps is not None and progress.global_step >= args.max_steps
            )
            if max_steps_reached:
                stop_reason = "max-steps"
            elif early_stop:
                stop_reason = "early-stopping"
            stop_requested = max_steps_reached or early_stop
            checkpoint_due = progress.global_step % args.checkpoint_every == 0
            if checkpoint_due or validation_due or stop_requested:
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
                    development_state=development_state,
                )
                last_checkpoint_step = progress.global_step
            if stop_requested:
                break

    if progress.loss_count == 0 or progress.final_loss is None:
        raise RuntimeError("training completed no optimizer steps")
    if development_state is None or progress.global_step % args.validation_every:
        validate_and_update(progress.global_step)
    if progress.global_step != last_checkpoint_step:
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
            development_state=development_state,
        )
    if stop_reason is None and progress.epoch_index >= args.epochs:
        stop_reason = "epochs-complete"
    complete = args.max_steps is None and stop_reason in {"epochs-complete", "early-stopping"}
    best_report = development_state["best_report"]
    best_macro_f1 = float(best_report["candidate"]["ner_macro_f1"])
    pilot_quality_pass = best_macro_f1 >= args.pilot_min_macro_f1
    final_model = args.output / "model"
    if final_model.exists():
        shutil.rmtree(final_model)
    shutil.copytree(args.output / "development-best/model", final_model)
    elapsed = time.perf_counter() - started
    manifest = {
        "schema_version": 1,
        "model_id": "hushmark-berturk-span-candidate",
        "architecture": "berturk-fixed-span-ner",
        "base_model": BASE_MODEL_ID,
        "base_revision": args.base_revision,
        "run_kind": "full" if complete else "pilot",
        "complete": complete,
        "adoption_eligible": False,
        "stop_reason": stop_reason,
        "examples": len(records),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "optimizer_steps": progress.global_step,
        "expected_optimizer_steps": expected_steps,
        "max_steps": args.max_steps,
        "mean_loss": progress.loss_sum / progress.loss_count,
        "final_loss": progress.final_loss,
        "elapsed_seconds": elapsed,
        "amp": amp_mode,
        "encoder_learning_rate": args.encoder_learning_rate,
        "head_learning_rate": args.head_learning_rate,
        "max_length": args.max_length,
        "max_width": args.max_width,
        "required_gold_max_width": required_max_width,
        "training_records_sha256": config["training_records_sha256"],
        "training_sources": sorted({str(record.get("source")) for record in records}),
        "replay_ratio": args.replay_ratio,
        "development_best_step": development_state["best_step"],
        "development_best_report": best_report,
        "development_macro_f1": best_macro_f1,
        "pilot_min_macro_f1": args.pilot_min_macro_f1,
        "pilot_quality_pass": pilot_quality_pass,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "resumed_from": resumed_from,
        "run_fingerprint": fingerprint,
        "hardware": hardware_manifest(torch, args.device),
        "artifact_files": {
            path.relative_to(final_model).as_posix(): {
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(final_model.rglob("*"))
            if path.is_file()
        },
    }
    atomic_write_json(args.output / "training_manifest.json", manifest)
    print(json.dumps(manifest, sort_keys=True), flush=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized-full-run", action="store_true")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--validation-suite", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--evaluation-suite", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--base-revision", default=BASE_MODEL_REVISION)
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--encoder-learning-rate", type=float, default=1e-5)
    parser.add_argument("--head-learning-rate", type=float, default=5e-5)
    parser.add_argument("--warmup-steps", type=int, default=500)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-width", type=int, default=24)
    parser.add_argument("--negative-ratio", type=int, default=8)
    parser.add_argument("--minimum-negatives", type=int, default=16)
    parser.add_argument("--replay-source", default="synthetic-full")
    parser.add_argument("--new-source", default="hushmark-dataset-prep-v1")
    parser.add_argument("--replay-ratio", type=float, default=0.70)
    parser.add_argument("--validation-every", type=int, default=500)
    parser.add_argument("--validation-batch-size", type=int, default=32)
    parser.add_argument("--validation-threshold", type=float, default=0.50)
    parser.add_argument("--validation-min-delta", type=float, default=0.002)
    parser.add_argument("--early-stopping-patience", type=int, default=3)
    parser.add_argument("--pilot-min-macro-f1", type=float, default=0.50)
    parser.add_argument("--checkpoint-every", type=int, default=500)
    parser.add_argument("--keep-checkpoints", type=int, default=2)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--amp", choices=("auto", "off", "bf16", "fp16"), default="auto")
    args = parser.parse_args()
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
