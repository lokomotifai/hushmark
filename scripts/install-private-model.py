#!/usr/bin/env python3
"""Install an immutable private Hugging Face model after full digest verification."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from huggingface_hub import snapshot_download
from hushmark_core.ner.registry import ModelSpec, load_model_spec

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_ID = "hushmark-berturk-112m"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_snapshot(snapshot: Path, spec: ModelSpec) -> None:
    """Verify every runtime file declared by the immutable model registry."""

    snapshot_root = snapshot.resolve()
    for relative_name, expected_size, expected_sha256 in spec.runtime_files:
        candidate = snapshot / relative_name
        if candidate.is_symlink():
            raise ValueError(f"private model snapshot contains a symlink: {relative_name}")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(snapshot_root):
            raise ValueError(f"private model path escapes the snapshot: {relative_name}")
        if not candidate.is_file():
            raise FileNotFoundError(f"private model snapshot is missing: {relative_name}")
        if candidate.stat().st_size != expected_size:
            raise ValueError(f"private model size verification failed: {relative_name}")
        if sha256_file(candidate) != expected_sha256:
            raise ValueError(f"private model SHA-256 verification failed: {relative_name}")


def copy_verified_snapshot(snapshot: Path, staging: Path, spec: ModelSpec) -> None:
    staging.mkdir(parents=True, exist_ok=False)
    for relative_name, _size, _sha256 in spec.runtime_files:
        source = snapshot / relative_name
        destination = staging / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    verify_snapshot(staging, spec)


def install_private_model(
    *,
    registry: Path,
    model_root: Path,
    model_id: str,
    force: bool,
    downloader: Callable[..., str] = snapshot_download,
) -> Path:
    spec = load_model_spec(registry, model_id)
    if spec.distribution != "private-huggingface":
        raise ValueError(f"model {model_id} is not a private Hugging Face artifact")
    if not model_id or Path(model_id).name != model_id:
        raise ValueError("model id cannot contain path components")

    model_root.mkdir(parents=True, exist_ok=True)
    target = model_root / model_id
    if target.exists() and not force:
        raise FileExistsError(f"model target already exists: {target}; pass --force to replace it")

    with tempfile.TemporaryDirectory(prefix=f".{model_id}-download-", dir=model_root) as temporary:
        download_root = Path(temporary) / "snapshot"
        returned_path = Path(
            downloader(
                repo_id=spec.source,
                revision=spec.revision,
                allow_patterns=[name for name, _size, _sha256 in spec.runtime_files],
                local_dir=download_root,
                token=True,
            )
        )
        verify_snapshot(returned_path, spec)
        staging = model_root / f".{model_id}-installing"
        if staging.exists():
            raise FileExistsError(f"stale model installation directory exists: {staging}")
        try:
            copy_verified_snapshot(returned_path, staging, spec)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    backup = model_root / f".{model_id}-backup"
    if backup.exists():
        shutil.rmtree(staging, ignore_errors=True)
        raise FileExistsError(f"stale model backup exists: {backup}")
    try:
        if target.exists():
            target.replace(backup)
        staging.replace(target)
    except BaseException:
        if backup.exists() and not target.exists():
            backup.replace(target)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "core" / "models.yaml")
    parser.add_argument("--model-root", type=Path, default=ROOT / "models")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    target = install_private_model(
        registry=args.registry,
        model_root=args.model_root,
        model_id=args.model_id,
        force=args.force,
    )
    print(f"installed and verified private model: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
