"""Single detection authority and deterministic overlap resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from hushmark_core.nlp import BlankSpacyNlpEngine
from hushmark_core.recognizers import SUPPORTED_LANGUAGES, build_recognizers
from hushmark_core.taxonomy_gen import ENTITY_TYPES, TAXONOMY

DETERMINISTIC_ENTITY_TYPES = [
    entity_type for entity_type in ENTITY_TYPES if TAXONOMY[entity_type]["layer"] == "deterministic"
]


@dataclass(frozen=True, slots=True)
class Entity:
    type: str
    start: int
    end: int
    confidence: float
    layer: Literal["deterministic", "ner"]


def spans_overlap(left: Entity, right: Entity) -> bool:
    return left.start < right.end and right.start < left.end


def resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Apply L0-first, then longest-span, then confidence precedence."""

    ranked = sorted(
        entities,
        key=lambda entity: (
            0 if entity.layer == "deterministic" else 1,
            -(entity.end - entity.start),
            -entity.confidence,
            entity.start,
            entity.type,
        ),
    )
    selected: list[Entity] = []
    for candidate in ranked:
        if not any(spans_overlap(candidate, current) for current in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda entity: (entity.start, entity.end, entity.type))


class DetectionEngine:
    """Presidio-backed L0 engine with a closed output taxonomy."""

    def __init__(self) -> None:
        nlp_engine = BlankSpacyNlpEngine()
        nlp_engine.load()
        registry = RecognizerRegistry(
            recognizers=build_recognizers(),
            supported_languages=list(SUPPORTED_LANGUAGES),
        )
        self._analyzer = AnalyzerEngine(
            registry=registry,
            nlp_engine=nlp_engine,
            supported_languages=list(SUPPORTED_LANGUAGES),
        )

    def analyze(self, text: str, language: str = "tr") -> list[Entity]:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {language}")
        results = self._analyzer.analyze(
            text=text,
            language=language,
            entities=DETERMINISTIC_ENTITY_TYPES,
            score_threshold=0.0,
        )
        entities: list[Entity] = []
        for result in results:
            if result.entity_type not in TAXONOMY:
                raise ValueError(f"recognizer emitted unknown entity type: {result.entity_type}")
            layer = TAXONOMY[result.entity_type]["layer"]
            entities.append(
                Entity(
                    type=result.entity_type,
                    start=result.start,
                    end=result.end,
                    confidence=result.score,
                    layer=layer,
                )
            )
        return resolve_overlaps(entities)


@lru_cache(maxsize=1)
def get_engine() -> DetectionEngine:
    return DetectionEngine()
