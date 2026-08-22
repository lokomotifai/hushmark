"""Lazy GLiNER checkpoint backend shared by training evaluators."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode import decode_predictions

from hushmark_bench.training import sha256_file


class CheckpointBackend:
    def __init__(
        self, checkpoint: Path, labels: Mapping[str, str], model_id: str, device: str
    ) -> None:
        self.checkpoint = checkpoint
        self._label_to_type = {label: entity_type for entity_type, label in labels.items()}
        self._model_id = model_id
        self._device = device
        self._model: Any | None = None
        self._weights = checkpoint / "pytorch_model.bin"
        self._sha256 = sha256_file(self._weights)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_sha256(self) -> str:
        return self._sha256

    def load(self) -> None:
        if self._model is None:
            gliner_class = importlib.import_module("gliner").GLiNER
            self._model = (
                gliner_class.from_pretrained(
                    str(self.checkpoint), local_files_only=True, map_location="cpu"
                )
                .to(self._device)
                .eval()
            )

    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        self.load()
        predictions = self._model.predict_entities(
            text, list(self._label_to_type), threshold=threshold
        )
        return decode_predictions(predictions, self._label_to_type)

    def predict_entities(
        self, text: str, labels: list[str], threshold: float
    ) -> list[dict[str, object]]:
        self.load()
        if set(labels) != set(self._label_to_type):
            raise ValueError("requested labels do not match the closed model taxonomy")
        return list(self._model.predict_entities(text, labels, threshold=threshold))
