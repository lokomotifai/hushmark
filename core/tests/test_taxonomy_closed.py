from __future__ import annotations

import pytest
from hushmark_core.engine import DetectionEngine
from hushmark_core.ner.base import NerSpan


class UnknownTypeBackend:
    @property
    def model_id(self) -> str:
        return "invalid"

    @property
    def model_sha256(self) -> None:
        return None

    def load(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        del text, threshold
        return [NerSpan("UNREGISTERED_TYPE", 0, 1, 0.9)]


def test_engine_rejects_type_outside_closed_taxonomy() -> None:
    engine = DetectionEngine(UnknownTypeBackend())
    with pytest.raises(ValueError, match="unknown entity type"):
        engine.analyze("x")
