"""Deterministic and recoverable state primitives for long training runs."""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
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
