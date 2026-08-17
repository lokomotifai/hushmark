"""In-process adapter for the Hushmark detection authority."""

from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from hushmark_core.config import Settings
from hushmark_core.engine import DetectionEngine
from hushmark_core.ner.registry import create_backend

from hushmark_bench.adapters import engine_slug


class CoreAdapter:
    def __init__(self, backend: Literal["disabled", "torch", "onnx"] = "onnx") -> None:
        self.runtime: str = backend
        settings = Settings(ner_backend=backend)
        ner_backend = create_backend(
            backend=backend,
            registry_path=settings.model_registry,
            model_root=settings.model_root,
            model_id=settings.model_id,
            onnx_model_file=settings.onnx_model_file,
        )
        self._engine = DetectionEngine(
            ner_backend,
            settings.ner_threshold,
            settings.ner_thresholds,
        )
        self.model_id = self._engine.model_id
        self.name = engine_slug("core", self.model_id, backend)
        self.model_sha256 = self._engine.model_sha256

    def predict(self, text: str) -> list[dict[str, object]]:
        return [asdict(entity) for entity in self._engine.analyze(text, "tr")]
