"""NER backend port shared by torch and ONNX adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NerSpan:
    entity_type: str
    start: int
    end: int
    confidence: float


class NerBackend(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def model_sha256(self) -> str | None: ...

    def load(self) -> None: ...

    def is_ready(self) -> bool: ...

    def predict(self, text: str, threshold: float) -> list[NerSpan]: ...


class DisabledNerBackend:
    @property
    def model_id(self) -> str:
        return "deterministic-v1"

    @property
    def model_sha256(self) -> None:
        return None

    def load(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        del text, threshold
        return []
