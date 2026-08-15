"""Pinned model registry parsing and backend selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hushmark_core.ner.base import DisabledNerBackend, NerBackend
from hushmark_core.ner.hf_token_classification import HfTokenClassificationBackend
from hushmark_core.ner.onnx_backend import OnnxNerBackend, OnnxUnsupported
from hushmark_core.ner.torch_backend import TorchNerBackend

ARCHITECTURES = frozenset({"gliner", "token-classification"})
DEFAULT_WEIGHT_FILE = "pytorch_model.bin"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    source: str
    revision: str
    distribution: str
    architecture: str
    weight_file: str
    sha256: str
    size: int
    labels: dict[str, tuple[str, ...]]
    label_to_type: dict[str, str]
    onnx_confidence_scale: float
    onnx_file: str | None
    onnx_size: int | None
    onnx_sha256: str | None
    runtime_files: tuple[tuple[str, int, str], ...]


@dataclass(frozen=True, slots=True)
class AvailableModel:
    id: str
    architecture: str
    backends: tuple[str, ...]


def load_registry_models(registry_path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, list):
        raise ValueError("model registry must contain a models list")
    return [model for model in models if isinstance(model, dict)]


def selectable_model_ids(models: list[dict[str, Any]]) -> list[str]:
    return [
        str(model["id"])
        for model in models
        if isinstance(model.get("id"), str) and isinstance(model.get("labels"), dict)
    ]


def normalize_labels(
    labels: dict[Any, Any], model_id: str
) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    normalized: dict[str, tuple[str, ...]] = {}
    label_to_type: dict[str, str] = {}
    for raw_type, raw_value in labels.items():
        entity_type = str(raw_type)
        model_labels: tuple[str, ...]
        if isinstance(raw_value, str):
            model_labels = (raw_value,)
        elif (
            isinstance(raw_value, list)
            and raw_value
            and all(isinstance(item, str) for item in raw_value)
        ):
            model_labels = tuple(str(item) for item in raw_value)
        else:
            raise ValueError(f"model {model_id} has an invalid label mapping for {entity_type}")
        normalized[entity_type] = model_labels
        for model_label in model_labels:
            if model_label in label_to_type:
                raise ValueError(
                    f"model {model_id} maps label {model_label!r} to multiple entity types"
                )
            label_to_type[model_label] = entity_type
    return normalized, label_to_type


def load_model_spec(registry_path: Path, model_id: str) -> ModelSpec:
    models = load_registry_models(registry_path)
    models_by_id = {str(model["id"]): model for model in models if isinstance(model.get("id"), str)}
    selectable = ", ".join(selectable_model_ids(models))
    model = models_by_id.get(model_id)
    if model is None:
        raise ValueError(f"unknown model id: {model_id}; selectable models: {selectable}")
    labels = model.get("labels")
    files = model.get("files")
    if not isinstance(files, list):
        raise ValueError(f"model {model_id} is missing files")
    if not isinstance(labels, dict):
        raise ValueError(
            f"model {model_id} is a tokenizer/config donor and is not selectable; "
            f"selectable models: {selectable}"
        )
    architecture = str(model.get("architecture", "gliner"))
    if architecture not in ARCHITECTURES:
        raise ValueError(f"model {model_id} has an unknown architecture: {architecture}")
    weight_file = str(model.get("weight_file", DEFAULT_WEIGHT_FILE))
    weight = next(
        (file for file in files if isinstance(file, dict) and file.get("path") == weight_file),
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
    string_labels, label_to_type = normalize_labels(labels, model_id)
    onnx_confidence_scale = float(model.get("onnx_confidence_scale", 1.0))
    if not 0.0 < onnx_confidence_scale <= 1.0:
        raise ValueError(f"model {model_id} has an invalid ONNX confidence scale")
    onnx_export = model.get("onnx_export")
    onnx_file: str | None = None
    onnx_size: int | None = None
    onnx_sha256: str | None = None
    if onnx_export is not None:
        if not isinstance(onnx_export, dict):
            raise ValueError(f"model {model_id} has an invalid pinned ONNX export")
        raw_onnx_file = onnx_export.get("file")
        raw_onnx_size = onnx_export.get("size")
        raw_onnx_sha256 = onnx_export.get("sha256")
        if (
            not isinstance(raw_onnx_file, str)
            or not isinstance(raw_onnx_size, int)
            or raw_onnx_size <= 0
            or not isinstance(raw_onnx_sha256, str)
            or len(raw_onnx_sha256) != 64
        ):
            raise ValueError(f"model {model_id} has an invalid pinned ONNX export")
        onnx_file = raw_onnx_file
        onnx_size = raw_onnx_size
        onnx_sha256 = raw_onnx_sha256
    runtime_config = model.get("runtime_config")
    if runtime_config is None:
        runtime_specs = [
            pinned_file(file, str(file["path"]), model_id)
            for file in files
            if isinstance(file, dict) and file.get("path") != weight_file
        ]
    else:
        if not isinstance(runtime_config, dict):
            raise ValueError(f"model {model_id} has an invalid runtime config declaration")
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
        runtime_specs = [pinned_file(source_spec, str(target_name), model_id)]
        if tokenizer_model_id == model_id:
            runtime_specs.extend(
                pinned_file(file, str(file["path"]), model_id)
                for file in files
                if isinstance(file, dict) and file.get("path") not in {source_name, weight_file}
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
        architecture=architecture,
        weight_file=weight_file,
        sha256=weight["sha256"],
        size=weight["size"],
        labels=string_labels,
        label_to_type=label_to_type,
        onnx_confidence_scale=onnx_confidence_scale,
        onnx_file=onnx_file,
        onnx_size=onnx_size,
        onnx_sha256=onnx_sha256,
        runtime_files=tuple(runtime_specs),
    )


def list_available_models(registry_path: Path) -> list[AvailableModel]:
    available: list[AvailableModel] = []
    for model_id in selectable_model_ids(load_registry_models(registry_path)):
        spec = load_model_spec(registry_path, model_id)
        backends = ("torch", "onnx") if spec.onnx_file is not None else ("torch",)
        available.append(
            AvailableModel(id=spec.id, architecture=spec.architecture, backends=backends)
        )
    return available


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
        if spec.architecture == "token-classification":
            return HfTokenClassificationBackend(model_dir=model_dir, spec=spec)
        return TorchNerBackend(model_dir=model_dir, spec=spec)
    if backend == "onnx":
        if spec.architecture != "gliner":
            raise OnnxUnsupported(
                f"model {model_id} has no ONNX runtime; token-classification models "
                "currently run on the torch backend only"
            )
        if spec.onnx_file is None:
            raise OnnxUnsupported(
                f"model {model_id} has no pinned ONNX export; use the torch backend"
            )
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
