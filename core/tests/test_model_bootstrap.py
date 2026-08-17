"""Model bootstrap must materialize runtime artifacts the integrity check accepts."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from hushmark_core.ner.integrity import verify_runtime_artifacts
from hushmark_core.ner.registry import load_model_spec

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "fetch-models.py"

CONFIG_BODY = json.dumps({"model_name": "test", "max_width": 12}, indent=2)


def load_bootstrap() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_models", BOOTSTRAP)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_entry(path: Path, name: str) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture
def local_model(tmp_path: Path) -> tuple[Path, Path]:
    model_root = tmp_path / "models"
    model_dir = model_root / "demo-model"
    model_dir.mkdir(parents=True)
    (model_dir / "gliner_config.source.json").write_text(CONFIG_BODY, encoding="utf-8")
    (model_dir / "pytorch_model.bin").write_bytes(b"weights")
    (model_dir / "tokenizer.json").write_bytes(b"tokenizer")
    (model_dir / "tokenizer_config.json").write_bytes(b"tokenizer-config")
    registry = {
        "models": [
            {
                "id": "demo-model",
                "source": "local/demo",
                "revision": "0" * 64,
                "distribution": "local-artifact",
                "files": [
                    file_entry(model_dir / name, name)
                    for name in (
                        "gliner_config.source.json",
                        "pytorch_model.bin",
                        "tokenizer.json",
                        "tokenizer_config.json",
                    )
                ],
                "runtime_config": {
                    "source": "gliner_config.source.json",
                    "target": "gliner_config.json",
                    "tokenizer_model": "demo-model",
                },
                "onnx_export": {"file": "model.onnx", "size": 10, "sha256": "a" * 64},
                "labels": {"PERSON": "person"},
            }
        ]
    }
    registry_path = tmp_path / "models.yaml"
    registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
    return registry_path, model_root


def test_materialized_runtime_config_passes_integrity(
    local_model: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path, model_root = local_model
    module = load_bootstrap()
    monkeypatch.setattr(module, "ROOT", registry_path.parent)
    monkeypatch.setattr(module, "REGISTRY", registry_path)
    monkeypatch.setattr(module, "MODEL_ROOT", model_root)

    assert module.main() == 0

    spec = load_model_spec(registry_path, "demo-model")
    verify_runtime_artifacts(model_root / "demo-model", spec)


def test_materialized_runtime_config_is_byte_identical_to_source(
    local_model: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path, model_root = local_model
    module = load_bootstrap()
    monkeypatch.setattr(module, "ROOT", registry_path.parent)
    monkeypatch.setattr(module, "REGISTRY", registry_path)
    monkeypatch.setattr(module, "MODEL_ROOT", model_root)

    assert module.main() == 0

    model_dir = model_root / "demo-model"
    source = (model_dir / "gliner_config.source.json").read_bytes()
    assert (model_dir / "gliner_config.json").read_bytes() == source
