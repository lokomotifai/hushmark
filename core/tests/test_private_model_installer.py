from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_installer() -> ModuleType:
    script = ROOT / "scripts" / "install-private-model.py"
    spec = importlib.util.spec_from_file_location("hushmark_private_model_installer", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load private model installer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_registry(path: Path, payload: bytes) -> None:
    primary_sha256 = hashlib.sha256(payload).hexdigest()
    artifact_sha256 = hashlib.sha256(
        f"{primary_sha256}  encoder/model.safetensors\n".encode()
    ).hexdigest()
    path.write_text(
        yaml.safe_dump(
            {
                "models": [
                    {
                        "id": "private-test-model",
                        "architecture": "berturk-fixed-span-ner",
                        "source": "lokomotifai/private-test-model",
                        "revision": "1" * 40,
                        "distribution": "private-huggingface",
                        "primary_file": "encoder/model.safetensors",
                        "artifact_sha256": artifact_sha256,
                        "files": [
                            {
                                "path": "encoder/model.safetensors",
                                "size": len(payload),
                                "sha256": primary_sha256,
                            }
                        ],
                        "labels": {"PERSON": "person"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_installer_downloads_exact_revision_and_atomically_installs(tmp_path: Path) -> None:
    module = load_installer()
    payload = b"private-model"
    registry = tmp_path / "models.yaml"
    model_root = tmp_path / "models"
    write_registry(registry, payload)
    observed: dict[str, Any] = {}

    def fake_download(**kwargs: Any) -> str:
        observed.update(kwargs)
        local_dir = Path(kwargs["local_dir"])
        target = local_dir / "encoder" / "model.safetensors"
        target.parent.mkdir(parents=True)
        target.write_bytes(payload)
        return str(local_dir)

    target = module.install_private_model(
        registry=registry,
        model_root=model_root,
        model_id="private-test-model",
        force=False,
        downloader=fake_download,
    )

    assert target == model_root / "private-test-model"
    assert (target / "encoder" / "model.safetensors").read_bytes() == payload
    assert observed["repo_id"] == "lokomotifai/private-test-model"
    assert observed["revision"] == "1" * 40
    assert observed["allow_patterns"] == ["encoder/model.safetensors"]
    assert observed["token"] is True
    assert not list(model_root.glob(".*-installing"))


def test_installer_rejects_tampered_download_without_replacing_target(tmp_path: Path) -> None:
    module = load_installer()
    payload = b"private-model"
    registry = tmp_path / "models.yaml"
    model_root = tmp_path / "models"
    target = model_root / "private-test-model"
    target.mkdir(parents=True)
    (target / "existing.txt").write_text("keep", encoding="utf-8")
    write_registry(registry, payload)

    def fake_download(**kwargs: Any) -> str:
        local_dir = Path(kwargs["local_dir"])
        downloaded = local_dir / "encoder" / "model.safetensors"
        downloaded.parent.mkdir(parents=True)
        downloaded.write_bytes(b"tampered")
        return str(local_dir)

    with pytest.raises(ValueError, match="size verification"):
        module.install_private_model(
            registry=registry,
            model_root=model_root,
            model_id="private-test-model",
            force=True,
            downloader=fake_download,
        )

    assert (target / "existing.txt").read_text(encoding="utf-8") == "keep"
