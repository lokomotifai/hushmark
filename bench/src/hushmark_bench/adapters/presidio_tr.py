"""Presidio configured for Turkish: built-in recognizers plus a Turkish NER recognizer.

This is the fair-competitor baseline. Presidio ships no Turkish model, so a Turkish
deployment is expected to register a transformer recognizer the way this adapter does.
No Turkish-specific identifier logic (TCKN, VKN, SGK, plate) is added, because Presidio
ships none; that gap is a finding, not a handicap imposed by the harness.

Subword aggregation must not be "simple": that strategy splits Turkish names into
fragments ("Şenkal" -> "Şen" + "kal"), which would understate the competitor because of
harness integration rather than model quality.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, cast

from hushmark_core.nlp import BlankSpacyNlpEngine
from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    PhoneRecognizer,
)
from tldextract import TLDExtract

DEFAULT_NER_MODEL = "akdeniz27/bert-base-turkish-cased-ner"

PATTERN_TYPE_MAP = {
    "CREDIT_CARD": "CREDIT_CARD",
    "EMAIL_ADDRESS": "EMAIL",
    "IBAN_CODE": "IBAN_OTHER",
    "PHONE_NUMBER": "TR_PHONE",
}

NER_TYPE_MAP = {
    "PER": "PERSON",
    "PERSON": "PERSON",
    "ORG": "ORG",
    "LOC": "ADDRESS",
    "LOCATION": "ADDRESS",
}


class TurkishNerRecognizer(EntityRecognizer):
    """Wraps a Turkish token-classification model as a Presidio recognizer."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._pipeline: Any = None
        super().__init__(
            supported_entities=["PERSON", "ORG", "ADDRESS"],
            supported_language="tr",
            name="TurkishTransformersRecognizer",
        )

    def load(self) -> None:
        if self._pipeline is not None:
            return
        transformers = importlib.import_module("transformers")
        self._pipeline = transformers.pipeline(
            "token-classification",
            model=self._model_name,
            aggregation_strategy="average",
            device=-1,
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        if self._pipeline is None:
            self.load()
        results: list[RecognizerResult] = []
        for prediction in cast(list[dict[str, Any]], self._pipeline(text)):
            entity_type = NER_TYPE_MAP.get(str(prediction.get("entity_group", "")))
            if entity_type is None or entity_type not in entities:
                continue
            results.append(
                RecognizerResult(
                    entity_type=entity_type,
                    start=int(prediction["start"]),
                    end=int(prediction["end"]),
                    score=float(prediction["score"]),
                )
            )
        return results


class PresidioTurkishAdapter:
    name = "presidio-tr"
    runtime = "torch"
    model_sha256: str | None = None

    def __init__(self) -> None:
        tldextract_runtime = importlib.import_module("tldextract.tldextract")
        tldextract_runtime.__dict__["TLD_EXTRACTOR"] = TLDExtract(
            cache_dir=None,
            suffix_list_urls=(),
        )
        ner_model = os.environ.get("HUSHMARK_BENCH_TR_NER_MODEL", DEFAULT_NER_MODEL)
        self.model_id = f"presidio-builtins+{ner_model}"
        nlp_engine = BlankSpacyNlpEngine()
        nlp_engine.load()
        recognizer = TurkishNerRecognizer(ner_model)
        recognizer.load()
        registry = RecognizerRegistry(
            recognizers=[
                CreditCardRecognizer(supported_language="tr"),
                EmailRecognizer(supported_language="tr"),
                IbanRecognizer(supported_language="tr"),
                PhoneRecognizer(supported_language="tr", supported_regions=["TR"]),
                recognizer,
            ],
            supported_languages=["tr"],
        )
        self._engine = AnalyzerEngine(
            registry=registry,
            nlp_engine=nlp_engine,
            supported_languages=["tr"],
        )
        self._entities = sorted(set(PATTERN_TYPE_MAP) | {"PERSON", "ORG", "ADDRESS"})

    def predict(self, text: str) -> list[dict[str, object]]:
        predictions: list[dict[str, object]] = []
        for result in self._engine.analyze(
            text=text,
            language="tr",
            entities=self._entities,
            score_threshold=0.0,
        ):
            entity_type = PATTERN_TYPE_MAP.get(result.entity_type, result.entity_type)
            value = text[result.start : result.end].replace(" ", "").replace("-", "")
            if result.entity_type == "IBAN_CODE" and value.startswith("TR"):
                entity_type = "TR_IBAN"
            predictions.append(
                {
                    "type": entity_type,
                    "start": result.start,
                    "end": result.end,
                    "confidence": result.score,
                    "layer": "deterministic" if result.entity_type in PATTERN_TYPE_MAP else "ner",
                }
            )
        return predictions
