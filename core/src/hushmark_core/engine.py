"""Single detection authority and deterministic overlap resolution."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from hushmark_core.config import get_settings
from hushmark_core.ner import DisabledNerBackend, NerBackend
from hushmark_core.ner.registry import create_backend
from hushmark_core.nlp import BlankSpacyNlpEngine
from hushmark_core.recognizers import SUPPORTED_LANGUAGES, build_recognizers
from hushmark_core.taxonomy_gen import ENTITY_TYPES, TAXONOMY

DETERMINISTIC_ENTITY_TYPES = [
    entity_type for entity_type in ENTITY_TYPES if TAXONOMY[entity_type]["layer"] == "deterministic"
]
_ALPHA_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
_NER_NEUTRAL_TOKENS = frozenset({"and", "ile", "or", "the", "ve", "veya"})


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


def requires_ner(text: str, deterministic_entities: list[Entity]) -> bool:
    """Skip model inference only for provably neutral residual text.

    Deterministic values are blanked without changing offsets. Remaining digits may be a
    date of birth or another NER-owned value, while any non-stopword alphabetic token may
    be a name, address, organization, or special-category reference.
    """

    residual = list(text)
    for entity in deterministic_entities:
        if entity.layer == "deterministic":
            residual[entity.start : entity.end] = " " * (entity.end - entity.start)
    residual_text = "".join(residual)
    if any(character.isdigit() for character in residual_text):
        return True
    return any(token not in _NER_NEUTRAL_TOKENS for token in _ALPHA_TOKEN.findall(residual_text))


class DetectionEngine:
    """Presidio-backed L0 engine with a closed output taxonomy."""

    def __init__(
        self,
        ner_backend: NerBackend | None = None,
        ner_threshold: float = 0.55,
        ner_thresholds: Mapping[str, float] | None = None,
    ) -> None:
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
        self._ner_backend = ner_backend or DisabledNerBackend()
        self._ner_threshold = ner_threshold
        self._ner_thresholds = dict(ner_thresholds or {})
        self._ner_backend.load()

    @property
    def model_id(self) -> str:
        return self._ner_backend.model_id

    @property
    def model_sha256(self) -> str | None:
        return self._ner_backend.model_sha256

    @property
    def ready(self) -> bool:
        return self._ner_backend.is_ready()

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
        query_threshold = min(self._ner_thresholds.values(), default=self._ner_threshold)
        ner_results = (
            self._ner_backend.predict(text, query_threshold) if requires_ner(text, entities) else []
        )
        for ner_result in ner_results:
            if ner_result.entity_type not in TAXONOMY:
                raise ValueError(
                    f"NER backend emitted unknown entity type: {ner_result.entity_type}"
                )
            type_threshold = self._ner_thresholds.get(ner_result.entity_type, self._ner_threshold)
            if ner_result.confidence < type_threshold:
                continue
            entities.append(
                Entity(
                    type=ner_result.entity_type,
                    start=ner_result.start,
                    end=ner_result.end,
                    confidence=ner_result.confidence,
                    layer="ner",
                )
            )
        return resolve_overlaps(entities)


@lru_cache(maxsize=1)
def get_engine() -> DetectionEngine:
    settings = get_settings()
    backend = create_backend(
        backend=settings.ner_backend,
        registry_path=settings.model_registry,
        model_root=settings.model_root,
        model_id=settings.model_id,
        onnx_model_file=settings.onnx_model_file,
    )
    return DetectionEngine(backend, settings.ner_threshold, settings.ner_thresholds)
