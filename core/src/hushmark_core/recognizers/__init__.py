"""Deterministic recognizer registry."""

from __future__ import annotations

from presidio_analyzer import EntityRecognizer

from hushmark_core.recognizers.credit_card import CreditCardRecognizer
from hushmark_core.recognizers.email import EmailRecognizer
from hushmark_core.recognizers.iban import IbanRecognizer
from hushmark_core.recognizers.phone import PhoneRecognizer
from hushmark_core.recognizers.plate import PlateRecognizer
from hushmark_core.recognizers.secrets import SecretsRecognizer
from hushmark_core.recognizers.sgk import SgkRecognizer
from hushmark_core.recognizers.tckn import TcknRecognizer
from hushmark_core.recognizers.vkn import VknRecognizer

SUPPORTED_LANGUAGES = ("tr", "en")


def build_recognizers() -> list[EntityRecognizer]:
    recognizers: list[EntityRecognizer] = []
    recognizer_types = (
        TcknRecognizer,
        VknRecognizer,
        IbanRecognizer,
        CreditCardRecognizer,
        PhoneRecognizer,
        PlateRecognizer,
        SgkRecognizer,
        EmailRecognizer,
        SecretsRecognizer,
    )
    for language in SUPPORTED_LANGUAGES:
        recognizers.extend(recognizer_type(language) for recognizer_type in recognizer_types)
    return recognizers
