#!/usr/bin/env python3
"""Build a deterministic, minimal bundle of the approved new GLiNER dataset views."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
BUNDLE_ROOT = f"hushmark-replay-data-{VERSION}"
FILES = {
    "data/new/train.jsonl": ROOT
    / "dataset-prep/prepared/v1/tasks/gliner_hushmark/splits/train.jsonl",
    "data/new/validation.jsonl": ROOT
    / "dataset-prep/prepared/v1/tasks/gliner_hushmark/evaluation/splits/validation.jsonl",
    "data/new/test_locked.jsonl": ROOT
    / "dataset-prep/prepared/v1/tasks/gliner_hushmark/evaluation/splits/test_locked.jsonl",
    "data/new/label_map.json": ROOT
    / "dataset-prep/prepared/v1/tasks/gliner_hushmark/label_map.json",
    "data/new/preparation_report.json": ROOT
    / "dataset-prep/prepared/v1/reports/preparation_report.json",
    "data/new/DATASET_CARD.md": ROOT / "dataset-prep/prepared/v1/DATASET_CARD.md",
    "data/new/DATA_GOVERNANCE.md": ROOT
    / "dataset-prep/prepared/v1/DATA_GOVERNANCE.md",
    "scripts/verify-training-data-bundle.py": ROOT
    / "scripts/verify-training-data-bundle.py",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tar_entry(archive: tarfile.TarFile, name: str, content: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(content))


def build(output: Path) -> str:
    canary = ("HUSHMARK-CORPUS-" + "CANARY-7f3a9d").encode()
    selected: dict[str, tuple[bytes, int, str]] = {}
    for target, source in sorted(FILES.items()):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"training data input is missing or a symlink: {source}")
        content = source.read_bytes()
        if canary in content:
            raise ValueError(f"private corpus canary found in training data input: {source}")
        mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
        selected[target] = (content, mode, source.relative_to(ROOT).as_posix())

    manifest = {
        "schema_version": 1,
        "bundle": BUNDLE_ROOT,
        "version": VERSION,
        "purpose": "Hushmark approved replay fine-tuning data",
        "files": [
            {
                "path": target,
                "source_path": source,
                "sha256": sha256_bytes(content),
                "size": len(content),
            }
            for target, (content, _, source) in selected.items()
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    payload: dict[str, tuple[bytes, int]] = {
        target: (content, mode) for target, (content, mode, _) in selected.items()
    }
    payload["BUNDLE-MANIFEST.json"] = (manifest_bytes, 0o644)
    checksums = "".join(
        f"{sha256_bytes(content)}  {path}\n"
        for path, (content, _) in sorted(payload.items())
    ).encode()
    payload["SHA256SUMS"] = (checksums, 0o644)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    with (
        temporary.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for relative, (content, mode) in sorted(payload.items()):
            tar_entry(archive, f"{BUNDLE_ROOT}/{relative}", content, mode)
    os.replace(temporary, output)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / f"{BUNDLE_ROOT}.tar.gz",
    )
    args = parser.parse_args()
    digest = build(args.output)
    print(f"wrote {args.output} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
