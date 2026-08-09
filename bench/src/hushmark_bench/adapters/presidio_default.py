"""Before-baseline adapter using only Presidio's built-in English recognizers."""

from __future__ import annotations

import importlib

from hushmark_core.nlp import BlankSpacyNlpEngine
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    PhoneRecognizer,
)
from tldextract import TLDExtract

TYPE_MAP = {
    "CREDIT_CARD": "CREDIT_CARD",
    "EMAIL_ADDRESS": "EMAIL",
    "IBAN_CODE": "IBAN_OTHER",
    "PHONE_NUMBER": "TR_PHONE",
}


class PresidioDefaultAdapter:
    name = "presidio-default"
    model_id = "presidio-builtins-en"
    model_sha256: str | None = None

    def __init__(self) -> None:
        tldextract_runtime = importlib.import_module("tldextract.tldextract")
        tldextract_runtime.__dict__["TLD_EXTRACTOR"] = TLDExtract(
            cache_dir=None,
            suffix_list_urls=(),
        )
        nlp_engine = BlankSpacyNlpEngine()
        nlp_engine.load()
        registry = RecognizerRegistry(
            recognizers=[
                CreditCardRecognizer(),
                EmailRecognizer(),
                IbanRecognizer(),
                PhoneRecognizer(),
            ],
            supported_languages=["en"],
        )
        self._engine = AnalyzerEngine(
            registry=registry,
            nlp_engine=nlp_engine,
            supported_languages=["en"],
        )

    def predict(self, text: str) -> list[dict[str, object]]:
        predictions: list[dict[str, object]] = []
        for result in self._engine.analyze(
            text=text,
            language="en",
            entities=list(TYPE_MAP),
            score_threshold=0.0,
        ):
            entity_type = TYPE_MAP.get(result.entity_type)
            if entity_type is None:
                continue
            value = text[result.start : result.end].replace(" ", "").replace("-", "")
            if result.entity_type == "IBAN_CODE" and value.startswith("TR"):
                entity_type = "TR_IBAN"
            predictions.append(
                {
                    "type": entity_type,
                    "start": result.start,
                    "end": result.end,
                    "confidence": result.score,
                    "layer": "deterministic",
                }
            )
        return predictions
