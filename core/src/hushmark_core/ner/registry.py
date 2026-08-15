"""Pinned model registry parsing and backend selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hushmark_core.ner.base import DisabledNerBackend, NerBackend
from hushmark_core.ner.onnx_backend import OnnxNerBackend
from hushmark_core.ner.torch_backend import TorchNerBackend


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    source: str
    revision: str
    distribution: str
    sha256: str
    size: int
    labels: dict[str, str]
    onnx_confidence_scale: float
    onnx_file: str
    onnx_size: int
    onnx_sha256: str
    runtime_files: tuple[tuple[str, int, str], ...]


def load_model_spec(registry_path: Path, model_id: str) -> ModelSpec:
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, list):
        raise ValueError("model registry must contain a models list")
    models_by_id = {
        str(model["id"]): model
        for model in models
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    }
    for model in models:
        if not isinstance(model, dict) or model.get("id") != model_id:
            continue
        labels = model.get("labels")
        files = model.get("files")
        if not isinstance(labels, dict) or not isinstance(files, list):
            raise ValueError(f"model {model_id} is missing labels or files")
        weight = next(
            (
                file
                for file in files
                if isinstance(file, dict) and file.get("path") == "pytorch_model.bin"
            ),
            None,
        )
        if (
            not isinstance(weight, dict)
            or not isinstance(weight.get("sha256"), str)
            or not isinstance(weight.get("size"), int)
            or weight["size"] <= 0
        ):
            raise ValueError(f"model {model_id} has no pinned weight SHA-256")
        distribution = str(model.get("distribution", "remote"))
        if distribution not in {"remote", "local-artifact"}:
            raise ValueError(f"model {model_id} has an invalid distribution")
        string_labels = {str(entity_type): str(label) for entity_type, label in labels.items()}
        onnx_confidence_scale = float(model.get("onnx_confidence_scale", 1.0))
        if not 0.0 < onnx_confidence_scale <= 1.0:
            raise ValueError(f"model {model_id} has an invalid ONNX confidence scale")
        onnx_export = model.get("onnx_export")
        if not isinstance(onnx_export, dict):
            raise ValueError(f"model {model_id} has no pinned ONNX export")
        onnx_file = onnx_export.get("file")
        onnx_size = onnx_export.get("size")
        onnx_sha256 = onnx_export.get("sha256")
        if (
            not isinstance(onnx_file, str)
            or not isinstance(onnx_size, int)
            or onnx_size <= 0
            or not isinstance(onnx_sha256, str)
            or len(onnx_sha256) != 64
        ):
            raise ValueError(f"model {model_id} has an invalid pinned ONNX export")
        runtime_config = model.get("runtime_config")
        if not isinstance(runtime_config, dict):
            raise ValueError(f"model {model_id} has no runtime config declaration")
        source_name = runtime_config.get("source")
        target_name = runtime_config.get("target")
        tokenizer_model_id = runtime_config.get("tokenizer_model")
        if not all(
            isinstance(value, str) for value in (source_name, target_name, tokenizer_model_id)
        ):
            raise ValueError(f"model {model_id} has an invalid runtime config declaration")
        source_spec = next(
            (file for file in files if isinstance(file, dict) and file.get("path") == source_name),
            None,
        )
        tokenizer_model = models_by_id.get(str(tokenizer_model_id))
        tokenizer_files = (
            tokenizer_model.get("files") if isinstance(tokenizer_model, dict) else None
        )
        if not isinstance(source_spec, dict) or not isinstance(tokenizer_files, list):
            raise ValueError(f"model {model_id} has unpinned runtime dependencies")
        runtime_specs: list[tuple[str, int, str]] = [
            pinned_file(source_spec, str(target_name), model_id)
        ]
        if tokenizer_model_id == model_id:
            runtime_specs.extend(
                pinned_file(file, str(file["path"]), model_id)
                for file in files
                if isinstance(file, dict)
                and file.get("path") not in {source_name, "pytorch_model.bin"}
            )
        else:
            runtime_specs.extend(
                pinned_file(file, str(file["path"]), model_id)
                for file in tokenizer_files
                if isinstance(file, dict)
            )
        return ModelSpec(
            id=model_id,
            source=str(model["source"]),
            revision=str(model["revision"]),
            distribution=distribution,
            sha256=weight["sha256"],
            size=weight["size"],
            labels=string_labels,
            onnx_confidence_scale=onnx_confidence_scale,
            onnx_file=onnx_file,
            onnx_size=onnx_size,
            onnx_sha256=onnx_sha256,
            runtime_files=tuple(runtime_specs),
        )
    raise ValueError(f"unknown model id: {model_id}")


def pinned_file(file: dict[str, Any], runtime_name: str, model_id: str) -> tuple[str, int, str]:
    size = file.get("size")
    sha256 = file.get("sha256")
    if not isinstance(size, int) or size <= 0 or not isinstance(sha256, str) or len(sha256) != 64:
        raise ValueError(f"model {model_id} has an unpinned runtime artifact")
    return runtime_name, size, sha256


def create_backend(
    *,
    backend: str,
    registry_path: Path,
    model_root: Path,
    model_id: str,
    onnx_model_file: str,
) -> NerBackend:
    if backend == "disabled":
        return DisabledNerBackend()
    spec = load_model_spec(registry_path, model_id)
    model_dir = model_root / model_id
    if backend == "torch":
        return TorchNerBackend(model_dir=model_dir, spec=spec)
    if backend == "onnx":
        return OnnxNerBackend(
            model_dir=model_dir,
            spec=spec,
            onnx_model_file=onnx_model_file,
        )
    raise ValueError(f"unknown NER backend: {backend}")


def validate_registry_shape(registry_path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("model registry root must be an object")
    return raw
