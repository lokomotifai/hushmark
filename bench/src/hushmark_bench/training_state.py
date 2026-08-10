"""Deterministic and recoverable state primitives for long training runs."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CHECKPOINT_PATTERN = re.compile(r"^step-(\d{8})$")


@dataclass(frozen=True, slots=True)
class TrainingProgress:
    epoch_index: int
    next_sample_offset: int
    global_step: int
    loss_sum: float
    loss_count: int
    final_loss: float | None


def deterministic_epoch_indices(size: int, seed: int, epoch_index: int) -> list[int]:
    """Return a stable epoch permutation that can resume without replaying collator work."""

    if size <= 0:
        raise ValueError("training dataset must not be empty")
    indices = list(range(size))
    random.Random(f"{seed}:{epoch_index}").shuffle(indices)
    return indices


def deterministic_balanced_epoch_indices(
    records: list[Mapping[str, Any]],
    seed: int,
    epoch_index: int,
    *,
    maximum_weight: float = 4.0,
    empty_weight: float = 0.25,
) -> list[int]:
    """Sample a stable epoch while capping rare-label oversampling and empty NER rows."""

    if not records or maximum_weight < 1 or not 0 < empty_weight <= 1:
        raise ValueError("balanced sampling configuration is invalid")
    label_counts: Counter[str] = Counter()
    record_labels: list[set[str]] = []
    for record in records:
        ner = record.get("ner")
        if not isinstance(ner, list):
            raise ValueError("balanced sampling record has invalid NER spans")
        labels = {
            str(span[2])
            for span in ner
            if isinstance(span, list) and len(span) == 3 and isinstance(span[2], str)
        }
        record_labels.append(labels)
        label_counts.update(labels)
    if not label_counts:
        raise ValueError("balanced sampling requires at least one NER label")
    most_common = max(label_counts.values())
    weights = [
        max(min(maximum_weight, most_common / label_counts[label]) for label in labels)
        if labels
        else empty_weight
        for labels in record_labels
    ]
    return random.Random(f"balanced:{seed}:{epoch_index}").choices(
        range(len(records)),
        weights=weights,
        k=len(records),
    )


def normalized_progress(
    *,
    epoch_index: int,
    next_sample_offset: int,
    global_step: int,
    loss_sum: float,
    loss_count: int,
    final_loss: float | None,
    examples: int,
) -> TrainingProgress:
    """Move an end-of-epoch checkpoint to the next epoch boundary."""

    if next_sample_offset >= examples:
        epoch_index += 1
        next_sample_offset = 0
    return TrainingProgress(
        epoch_index=epoch_index,
        next_sample_offset=next_sample_offset,
        global_step=global_step,
        loss_sum=loss_sum,
        loss_count=loss_count,
        final_loss=final_loss,
    )


def run_fingerprint(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def optimizer_parameter_groups(
    model: Any,
    *,
    train_text_encoder: bool,
    encoder_learning_rate: float,
    head_learning_rate: float,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Build explicit encoder/head groups so the transformer never receives the head LR."""

    if encoder_learning_rate <= 0 or head_learning_rate <= 0:
        raise ValueError("learning rates must be positive")
    if not train_text_encoder:
        model.freeze_component("text_encoder")
    encoder: list[Any] = []
    head: list[Any] = []
    trainable: list[Any] = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        trainable.append(parameter)
        if name.startswith("token_rep_layer.bert_layer."):
            encoder.append(parameter)
        else:
            head.append(parameter)
    if not trainable or not head:
        raise RuntimeError("training configuration has no trainable head parameters")
    groups = [{"params": head, "lr": head_learning_rate, "group_name": "head"}]
    if encoder:
        groups.append(
            {
                "params": encoder,
                "lr": encoder_learning_rate,
                "group_name": "text_encoder",
            }
        )
    return groups, trainable


def linear_warmup_decay(step: int, *, warmup_steps: int, total_steps: int) -> float:
    if total_steps < 1 or warmup_steps < 0:
        raise ValueError("scheduler step counts are invalid")
    if warmup_steps and step < warmup_steps:
        return max(float(step + 1) / warmup_steps, 1.0 / warmup_steps)
    decay_steps = max(1, total_steps - warmup_steps)
    return max(0.0, float(total_steps - step) / decay_steps)


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def checkpoint_name(global_step: int) -> str:
    if global_step <= 0:
        raise ValueError("checkpoint step must be positive")
    return f"step-{global_step:08d}"


def write_latest_checkpoint(output: Path, checkpoint: Path) -> None:
    try:
        relative = checkpoint.resolve().relative_to(output.resolve())
    except ValueError as error:
        raise ValueError("checkpoint must be inside the output directory") from error
    atomic_write_json(
        output / "latest-checkpoint.json",
        {"schema_version": 1, "checkpoint": relative.as_posix()},
    )


def resolve_resume_checkpoint(output: Path, requested: Path | None) -> Path | None:
    if requested is None:
        return None
    if str(requested) == "latest":
        pointer_path = output / "latest-checkpoint.json"
        if not pointer_path.is_file():
            raise FileNotFoundError(f"latest checkpoint pointer is missing: {pointer_path}")
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        relative = pointer.get("checkpoint") if isinstance(pointer, dict) else None
        if not isinstance(relative, str):
            raise ValueError("latest checkpoint pointer is invalid")
        checkpoint = (output / relative).resolve()
        try:
            checkpoint.relative_to(output.resolve())
        except ValueError as error:
            raise ValueError("latest checkpoint escapes the output directory") from error
    else:
        checkpoint = requested.resolve()
    if not checkpoint.is_dir():
        raise FileNotFoundError(f"resume checkpoint is missing: {checkpoint}")
    if not (checkpoint / "checkpoint_manifest.json").is_file():
        raise FileNotFoundError(f"checkpoint manifest is missing: {checkpoint}")
    if not (checkpoint / "state.pt").is_file():
        raise FileNotFoundError(f"checkpoint state is missing: {checkpoint}")
    return checkpoint


def prune_checkpoints(checkpoints_dir: Path, keep: int) -> list[Path]:
    """Remove only recognized checkpoint directories, retaining the newest `keep`."""

    if keep < 1:
        raise ValueError("at least one checkpoint must be retained")
    checkpoints = sorted(
        path
        for path in checkpoints_dir.iterdir()
        if path.is_dir() and CHECKPOINT_PATTERN.fullmatch(path.name)
    )
    removed: list[Path] = []
    for checkpoint in checkpoints[:-keep]:
        checkpoint.resolve().relative_to(checkpoints_dir.resolve())
        shutil.rmtree(checkpoint)
        removed.append(checkpoint)
    return removed


def progress_dict(progress: TrainingProgress) -> dict[str, Any]:
    return asdict(progress)
