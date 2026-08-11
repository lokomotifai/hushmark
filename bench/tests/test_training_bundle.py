from __future__ import annotations

import hashlib
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_training_bundle_is_reproducible_allowlisted_and_self_verifying(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
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
    assert all(name.startswith("hushmark-ac1-training-0.1.0/") for name in names)
    assert not any("/bench/train/outputs/" in name for name in names)
    assert not any("/bench/external/" in name for name in names)
    assert not any("/bench/external-data/" in name for name in names)
    assert not any("/models/" in name for name in names)
    assert not any(part in {"briefs", "research"} for name in names for part in Path(name).parts)

    extracted = tmp_path / "extracted/hushmark-ac1-training-0.1.0"
    result = subprocess.run(
        ["python3", "scripts/verify-training-bundle.py"],
        cwd=extracted,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "allowlisted files" in result.stdout
