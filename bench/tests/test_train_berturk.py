from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "train_berturk", ROOT / "bench/train/train_berturk.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_named_paths_accept_locked_suite_names() -> None:
    assert MODULE.named_paths(["legacy_locked=/tmp/legacy.jsonl"]) == {
        "legacy_locked": Path("/tmp/legacy.jsonl")
    }
