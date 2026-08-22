#!/usr/bin/env python3
"""Build a deterministic, source-only replay-training bundle from an explicit allowlist."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
BUNDLE_ROOT = f"hushmark-replay-training-{VERSION}"
ROOT_FILES = (
    ".python-version",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/train-berturk-runpod.md",
    "docs/train-runpod.md",
    "pyproject.toml",
    "uv.lock",
)
SOURCE_DIRECTORIES = (
    "bench",
    "core",
    "sdk-py",
    "taxonomy",
    "tools/codegen",
)
SCRIPT_FILES = (
    "scripts/bootstrap-gpu.sh",
    "scripts/fetch-berturk.py",
    "scripts/fetch-models.py",
    "scripts/verify-training-data-bundle.py",
    "scripts/verify-training-bundle.py",
)
SKIP_NAMES = frozenset(
    {
        ".DS_Store",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "dist",
        "external",
        "external-data",
        "node_modules",
    }
)
FORBIDDEN_SEGMENTS = frozenset({"briefs", "hushmark", "research"})
FORBIDDEN_FILES = frozenset({"EXECUTABLE-PLAN-PROMPT.md", "PLAN-BRIEF.md", "PLAN.md"})


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def include_path(relative: Path) -> bool:
    normalized = relative.as_posix()
    return not (
        any(part in SKIP_NAMES for part in relative.parts)
        or normalized == "bench/train/outputs"
        or normalized.startswith("bench/train/outputs/")
    )


def iter_source_files(directory: Path) -> Iterator[Path]:
    """Walk a source tree without descending into local-only or generated directories."""
    for current, directories, filenames in os.walk(directory, topdown=True):
        current_path = Path(current)
        directories[:] = sorted(name for name in directories if name not in SKIP_NAMES)
        if current_path.relative_to(ROOT) == Path("bench/train"):
            directories[:] = [name for name in directories if name != "outputs"]
        for filename in sorted(filenames):
            yield current_path / filename


def collect_files() -> dict[str, tuple[bytes, int]]:
    selected: dict[str, tuple[bytes, int]] = {}
    candidates = [ROOT / path for path in ROOT_FILES]
    candidates.extend(ROOT / path for path in SCRIPT_FILES)
    for directory in SOURCE_DIRECTORIES:
        candidates.extend(iter_source_files(ROOT / directory))

    canary = ("HUSHMARK-CORPUS-" + "CANARY-7f3a9d").encode()
    for path in candidates:
        if path.is_symlink():
            raise ValueError(f"training bundle refuses symlink: {path.relative_to(ROOT)}")
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if not include_path(relative):
            continue
        if relative.name in FORBIDDEN_FILES or any(
            part in FORBIDDEN_SEGMENTS for part in relative.parts
        ):
            raise ValueError(f"private path selected for training bundle: {relative}")
        content = path.read_bytes()
        if canary in content:
            raise ValueError(f"private corpus canary found in selected file: {relative}")
        mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        selected[relative.as_posix()] = (content, mode)
    return dict(sorted(selected.items()))


def tar_entry(archive: tarfile.TarFile, name: str, content: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    archive.addfile(info, io.BytesIO(content))


def build(output: Path) -> str:
    files = collect_files()
    manifest = {
        "schema_version": 1,
        "bundle": BUNDLE_ROOT,
        "version": VERSION,
        "purpose": "Hushmark isolated replay GPU training",
        "files": [
            {"path": path, "sha256": sha256_bytes(content), "size": len(content)}
            for path, (content, _) in files.items()
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    files["BUNDLE-MANIFEST.json"] = (manifest_bytes, 0o644)
    checksums = "".join(
        f"{sha256_bytes(content)}  {path}\n" for path, (content, _) in sorted(files.items())
    ).encode()
    files["SHA256SUMS"] = (checksums, 0o644)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    with (
        temporary.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for relative, (content, mode) in sorted(files.items()):
            tar_entry(archive, f"{BUNDLE_ROOT}/{relative}", content, mode)
    os.replace(temporary, output)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
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
