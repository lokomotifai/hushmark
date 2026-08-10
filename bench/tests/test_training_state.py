from __future__ import annotations

import json
from pathlib import Path

import pytest
from hushmark_bench.training_state import (
    atomic_write_json,
    deterministic_epoch_indices,
    normalized_progress,
    prune_checkpoints,
    resolve_resume_checkpoint,
    run_fingerprint,
    write_latest_checkpoint,
)


def test_epoch_permutation_is_deterministic_and_epoch_specific() -> None:
    first = deterministic_epoch_indices(100, 20260809, 0)
    assert first == deterministic_epoch_indices(100, 20260809, 0)
    assert first != deterministic_epoch_indices(100, 20260809, 1)
    assert sorted(first) == list(range(100))


def test_progress_normalizes_end_of_epoch() -> None:
    progress = normalized_progress(
        epoch_index=1,
        next_sample_offset=10,
        global_step=7,
        loss_sum=3.5,
        loss_count=7,
        final_loss=0.25,
        examples=10,
    )
    assert progress.epoch_index == 2
    assert progress.next_sample_offset == 0
    assert progress.global_step == 7


def test_run_fingerprint_is_canonical() -> None:
    assert run_fingerprint({"b": 2, "a": 1}) == run_fingerprint({"a": 1, "b": 2})
    assert run_fingerprint({"a": 1}) != run_fingerprint({"a": 2})


def test_latest_checkpoint_round_trip_and_escape_rejection(tmp_path: Path) -> None:
    output = tmp_path / "run"
    checkpoint = output / "checkpoints/step-00000001"
    checkpoint.mkdir(parents=True)
    atomic_write_json(checkpoint / "checkpoint_manifest.json", {"schema_version": 1})
    (checkpoint / "state.pt").write_bytes(b"state")
    write_latest_checkpoint(output, checkpoint)
    assert resolve_resume_checkpoint(output, Path("latest")) == checkpoint.resolve()

    (output / "latest-checkpoint.json").write_text(
        json.dumps({"checkpoint": "../../outside"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="escapes"):
        resolve_resume_checkpoint(output, Path("latest"))


def test_checkpoint_pruning_touches_only_recognized_directories(tmp_path: Path) -> None:
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    for step in range(1, 5):
        (checkpoints / f"step-{step:08d}").mkdir()
    unrelated = checkpoints / "do-not-delete"
    unrelated.mkdir()
    removed = prune_checkpoints(checkpoints, keep=2)
    assert [path.name for path in removed] == ["step-00000001", "step-00000002"]
    assert unrelated.is_dir()
    assert (checkpoints / "step-00000003").is_dir()
    assert (checkpoints / "step-00000004").is_dir()
