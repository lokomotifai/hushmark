"""Shared primitives for deterministic recognizers and their Presidio adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts


@dataclass(frozen=True, slots=True)
class DetectorHit:
    """A validated deterministic match using code-point offsets."""

    entity_type: str
    start: int
    end: int
    score: float


Detector = Callable[[str], list[DetectorHit]]


class ValidatorRecognizer(EntityRecognizer):
    """Expose a pure deterministic detector through Presidio's recognizer port."""

    def __init__(
        self,
        *,
        name: str,
        supported_entities: list[str],
        detector: Detector,
        language: str,
    ) -> None:
        super().__init__(
            supported_entities=supported_entities,
            name=f"{name}-{language}",
            supported_language=language,
            version="0.1.0",
            country_code="TR",
        )
        self._detector = detector
        self._recognizer_name = name

    def load(self) -> None:
        """Pure validators have no external assets to load."""

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts,
    ) -> list[RecognizerResult]:
        """Return only requested, checksum-validated results."""

        del nlp_artifacts
        requested = set(entities)
        return [
            RecognizerResult(
                entity_type=hit.entity_type,
                start=hit.start,
                end=hit.end,
                score=hit.score,
                recognition_metadata={
                    "layer": "deterministic",
                    "recognizer": self._recognizer_name,
                },
            )
            for hit in self._detector(text)
            if hit.entity_type in requested
        ]
