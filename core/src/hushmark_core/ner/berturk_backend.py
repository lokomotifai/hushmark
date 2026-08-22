"""Offline adapter for Hushmark's fixed-label BERTurk span model."""

from __future__ import annotations

import hashlib
from hashlib import file_digest
from pathlib import Path

from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.berturk_span import BerturkSpanModel
from hushmark_core.ner.decode import decode_predictions
from hushmark_core.ner.integrity import verify_runtime_artifacts
from hushmark_core.ner.registry_types import ModelSpecLike


class BerturkNerBackend:
    """Load and run a fully local, integrity-checked BERTurk artifact."""

    def __init__(self, *, model_dir: Path, spec: ModelSpecLike) -> None:
        self._model_dir = model_dir
        self._spec = spec
        self._model: BerturkSpanModel | None = None
        self._measured_sha256: str | None = None
        self._label_to_type = {label: entity_type for entity_type, label in spec.labels.items()}

    @property
    def model_id(self) -> str:
        return self._spec.id

    @property
    def model_sha256(self) -> str | None:
        return self._measured_sha256

    def load(self) -> None:
        if self._model is not None:
            return
        primary_file = self._model_dir / self._spec.primary_file
        if not primary_file.is_file():
            raise FileNotFoundError(
                f"BERTurk model is not installed at {self._model_dir}; "
                "run scripts/install-private-model.py"
            )
        verify_runtime_artifacts(self._model_dir, self._spec)
        with primary_file.open("rb") as model_stream:
            measured_sha256 = file_digest(model_stream, "sha256").hexdigest()
        if measured_sha256 != self._spec.sha256:
            raise ValueError(f"BERTurk primary model SHA-256 verification failed: {primary_file}")
        artifact_manifest = "".join(
            f"{sha256}  {filename}\n"
            for filename, _size, sha256 in sorted(self._spec.runtime_files)
        )
        artifact_sha256 = hashlib.sha256(artifact_manifest.encode()).hexdigest()
        if artifact_sha256 != self._spec.artifact_sha256:
            raise ValueError("BERTurk aggregate artifact SHA-256 does not match the registry")
        model = BerturkSpanModel.load_artifact(self._model_dir, local_files_only=True)
        if set(model.label_names) != set(self._label_to_type):
            raise ValueError("BERTurk artifact labels do not match the pinned registry")
        self._model = model.eval()
        self._measured_sha256 = artifact_sha256

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
