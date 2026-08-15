"""Offline PyTorch GLiNER adapter."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from hashlib import file_digest
from pathlib import Path
from typing import Protocol, cast

from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode import decode_predictions
from hushmark_core.ner.integrity import verify_runtime_artifacts
from hushmark_core.ner.registry_types import ModelSpecLike


class PredictingModel(Protocol):
    def eval(self) -> PredictingModel: ...

    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> Sequence[Mapping[str, object]]: ...


class TorchNerBackend:
    def __init__(self, *, model_dir: Path, spec: ModelSpecLike) -> None:
        self._model_dir = model_dir
        self._spec = spec
        self._model: PredictingModel | None = None
        self._measured_sha256: str | None = None
        self._label_to_type = dict(spec.label_to_type)

    @property
    def model_id(self) -> str:
        return self._spec.id

    @property
    def model_sha256(self) -> str | None:
        return self._measured_sha256

    def load(self) -> None:
        if self._model is not None:
            return
        model_file = self._model_dir / self._spec.weight_file
        if not model_file.is_file():
            raise FileNotFoundError(
                f"model weights are not installed at {self._model_dir}; run scripts/fetch-models.py"
            )
        if model_file.stat().st_size != self._spec.size:
            raise ValueError(f"PyTorch model size verification failed: {model_file}")
        with model_file.open("rb") as model_stream:
            measured_sha256 = file_digest(model_stream, "sha256").hexdigest()
        if measured_sha256 != self._spec.sha256:
            raise ValueError(f"PyTorch model SHA-256 verification failed: {model_file}")
        verify_runtime_artifacts(self._model_dir, self._spec)
        self._measured_sha256 = measured_sha256
        gliner_module = importlib.import_module("gliner")
        gliner_class = gliner_module.GLiNER
        model = gliner_class.from_pretrained(
            str(self._model_dir),
            local_files_only=True,
            map_location="cpu",
        )
        self._model = cast(PredictingModel, model.eval())

    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        if self._model is None:
            self.load()
        assert self._model is not None
        predictions = self._model.predict_entities(
            text,
            list(self._label_to_type),
            threshold=threshold,
        )
        return decode_predictions(predictions, self._label_to_type)
