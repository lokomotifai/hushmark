from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "bench/train/prepare_replay.py"
SPEC = importlib.util.spec_from_file_location("prepare_replay", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
prepare_replay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prepare_replay
SPEC.loader.exec_module(prepare_replay)


def record(record_id: str, source: str, token: str) -> dict[str, object]:
    return {
        "id": record_id,
        "source": source,
        "tokenized_text": [token],
        "ner": [[0, 0, "person"]],
        "ner_labels": ["person"],
    }


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_replay_union_is_deterministic_and_records_provenance(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.jsonl"
    new = tmp_path / "new.jsonl"
    output = tmp_path / "mixed.jsonl"
    manifest = tmp_path / "manifest.json"
    write_rows(legacy, [record("legacy-1", "synthetic-full", "eski")])
    write_rows(new, [record("new-1", "hushmark-dataset-prep-v1", "yeni")])

    first = prepare_replay.build_replay_union(
        legacy_path=legacy,
        new_path=new,
        output_path=output,
        manifest_path=manifest,
        legacy_source="synthetic-full",
        new_source="hushmark-dataset-prep-v1",
    )
    first_bytes = output.read_bytes()
    second = prepare_replay.build_replay_union(
        legacy_path=legacy,
        new_path=new,
        output_path=output,
        manifest_path=manifest,
        legacy_source="synthetic-full",
        new_source="hushmark-dataset-prep-v1",
    )
    assert first == second
    assert output.read_bytes() == first_bytes
    assert first["output"]["records"] == 2
    assert first["cross_source_content_overlap"] == 0


def test_replay_union_rejects_model_visible_overlap(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.jsonl"
    new = tmp_path / "new.jsonl"
    write_rows(legacy, [record("legacy-1", "synthetic-full", "aynı")])
    write_rows(new, [record("new-1", "hushmark-dataset-prep-v1", "aynı")])
    with pytest.raises(ValueError, match="content overlap"):
        prepare_replay.build_replay_union(
            legacy_path=legacy,
            new_path=new,
            output_path=tmp_path / "mixed.jsonl",
            manifest_path=tmp_path / "manifest.json",
            legacy_source="synthetic-full",
            new_source="hushmark-dataset-prep-v1",
        )
