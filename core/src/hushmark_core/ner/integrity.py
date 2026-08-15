"""Runtime integrity checks for every model artifact consumed by GLiNER."""

from __future__ import annotations

from hashlib import file_digest
from pathlib import Path

from hushmark_core.ner.registry_types import ModelSpecLike


def verify_runtime_artifacts(model_dir: Path, spec: ModelSpecLike) -> None:
    for filename, expected_size, expected_sha256 in spec.runtime_files:
        path = model_dir / filename
        if not path.is_file() or path.stat().st_size != expected_size:
            raise ValueError(f"model artifact size verification failed: {path}")
        with path.open("rb") as stream:
            measured = file_digest(stream, "sha256").hexdigest()
        if measured != expected_sha256:
            raise ValueError(f"model artifact SHA-256 verification failed: {path}")
