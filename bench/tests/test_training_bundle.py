from __future__ import annotations

import hashlib
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DATASET_CARD = ROOT / "dataset-prep/prepared/v1/DATASET_CARD.md"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_training_bundle_is_reproducible_allowlisted_and_self_verifying(tmp_path: Path) -> None:
    first = tmp_path / "first-code.tar.gz"
    second = tmp_path / "second-code.tar.gz"
    for output in (first, second):
        subprocess.run(
            ["python3", "scripts/build-training-bundle.py", "--output", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    assert sha256_file(first) == sha256_file(second)

    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
        archive.extractall(tmp_path / "extracted", filter="data")
    assert names
    assert all(name.startswith("hushmark-replay-training-0.2.0/") for name in names)
    assert not any("/bench/train/outputs/" in name for name in names)
    assert not any("/bench/external/" in name for name in names)
    assert not any("/bench/external-data/" in name for name in names)
    assert not any("/models/" in name for name in names)
    assert not any(part in {"briefs", "research"} for name in names for part in Path(name).parts)

    extracted = tmp_path / "extracted/hushmark-replay-training-0.2.0"
    result = subprocess.run(
        ["python3", "scripts/verify-training-bundle.py"],
        cwd=extracted,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "allowlisted files" in result.stdout


def test_training_data_bundle_is_minimal_reproducible_and_self_verifying(
    tmp_path: Path,
) -> None:
    if not PRIVATE_DATASET_CARD.is_file():
        pytest.skip("private dataset-prep inputs are intentionally absent from source checkouts")
    first = tmp_path / "data-first.tar.gz"
    second = tmp_path / "data-second.tar.gz"
    for output in (first, second):
        subprocess.run(
            ["python3", "scripts/build-training-data-bundle.py", "--output", str(output)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    assert sha256_file(first) == sha256_file(second)

    with tarfile.open(first, "r:gz") as archive:
        names = archive.getnames()
        archive.extractall(tmp_path / "data-extracted", filter="data")
    assert names
    assert all(name.startswith("hushmark-replay-data-0.2.0/") for name in names)
    assert not any("research" in Path(name).parts for name in names)
    assert not any("books" in Path(name).parts for name in names)
    assert not any("public-documents" in name for name in names)

    extracted = tmp_path / "data-extracted/hushmark-replay-data-0.2.0"
    result = subprocess.run(
        ["python3", "scripts/verify-training-data-bundle.py"],
        cwd=extracted,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "allowlisted training data files" in result.stdout
