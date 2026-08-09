"""ONNX GLiNER adapter with an explicit unsupported-export state."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from hashlib import file_digest
from pathlib import Path
from typing import Protocol, cast

from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode import decode_predictions
from hushmark_core.ner.registry_types import ModelSpecLike


class OnnxUnsupported(RuntimeError):
    """The pinned model revision has no verified ONNX export."""


class OnnxPredictingModel(Protocol):
    def eval(self) -> OnnxPredictingModel: ...

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> Sequence[Mapping[str, object]]: ...


class OnnxNerBackend:
    def __init__(
        self,
        *,
        model_dir: Path,
        spec: ModelSpecLike,
        onnx_model_file: str,
    ) -> None:
        self._model_dir = model_dir
        self._spec = spec
        self._onnx_model_file = onnx_model_file
        self._model: OnnxPredictingModel | None = None
        self._label_to_type = {label: entity_type for entity_type, label in spec.labels.items()}

    @property
    def model_id(self) -> str:
        return self._spec.id

    @property
    def model_sha256(self) -> str:
        return self._spec.sha256

    def load(self) -> None:
        if self._model is not None:
            return
        model_file = self._model_dir / self._onnx_model_file
        if not model_file.is_file():
            raise OnnxUnsupported(
                f"verified ONNX export is absent for {self._spec.id}: {model_file}"
            )
        if self._onnx_model_file != self._spec.onnx_file:
            raise OnnxUnsupported("configured ONNX filename does not match the pinned registry")
        if model_file.stat().st_size != self._spec.onnx_size:
            raise OnnxUnsupported(f"ONNX size verification failed: {model_file}")
        with model_file.open("rb") as model_stream:
            digest = file_digest(model_stream, "sha256").hexdigest()
        if digest != self._spec.onnx_sha256:
            raise OnnxUnsupported(f"ONNX SHA-256 verification failed: {model_file}")
        gliner_module = importlib.import_module("gliner")
        gliner_class = gliner_module.GLiNER
        model = gliner_class.from_pretrained(
            str(self._model_dir),
            local_files_only=True,
            load_onnx_model=True,
            onnx_model_file=str(model_file),
        )
        self._model = cast(OnnxPredictingModel, model.eval())

    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        if self._model is None:
            self.load()
        assert self._model is not None
        predictions = self._model.predict_entities(
            text,
            list(self._label_to_type),
            threshold=threshold * self._spec.onnx_confidence_scale,
        )
        spans = decode_predictions(predictions, self._label_to_type)
        return [
            NerSpan(
                entity_type=span.entity_type,
                start=span.start,
                end=span.end,
                confidence=min(1.0, span.confidence / self._spec.onnx_confidence_scale),
            )
            for span in spans
        ]
