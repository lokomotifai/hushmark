"""Payment-card detection with Luhn validation."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def compact_card(value: str) -> str:
    return value.replace(" ", "").replace("-", "")


def validate_credit_card(value: str) -> bool:
    compact = compact_card(value)
    if not 13 <= len(compact) <= 19 or not compact.isascii() or not compact.isdigit():
        return False
    total = 0
    parity = len(compact) % 2
    for index, char in enumerate(compact):
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def detect_credit_card(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("CREDIT_CARD", match.start(), match.end(), 1.0)
        for match in CARD_PATTERN.finditer(text)
        if validate_credit_card(match.group())
    ]


class CreditCardRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="LuhnCreditCardRecognizer",
            supported_entities=["CREDIT_CARD"],
            detector=detect_credit_card,
            language=language,
        )
