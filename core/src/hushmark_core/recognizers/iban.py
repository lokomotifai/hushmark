"""ISO 13616 / ISO 7064 IBAN validation."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

IBAN_PATTERN = re.compile(
    r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}(?![A-Z0-9])",
    flags=re.ASCII,
)


def compact_iban(value: str) -> str:
    return value.replace(" ", "").replace("-", "")


def validate_iban(value: str) -> bool:
    """Validate ASCII format and the streaming mod-97 checksum without big integers."""

    compact = compact_iban(value)
    if not 15 <= len(compact) <= 34 or not compact.isascii() or not compact.isalnum():
        return False
    if not compact[:2].isalpha() or compact[:2].upper() != compact[:2]:
        return False
    if not compact[2:4].isdigit():
        return False
    if compact.startswith("TR") and (len(compact) != 26 or not compact[4:].isdigit()):
        return False
    rearranged = compact[4:] + compact[:4]
    remainder = 0
    for char in rearranged:
        encoded = str(ord(char) - 55) if char.isalpha() else char
        for digit in encoded:
            remainder = (remainder * 10 + int(digit)) % 97
    return remainder == 1


def detect_iban(text: str) -> list[DetectorHit]:
    hits: list[DetectorHit] = []
    for match in IBAN_PATTERN.finditer(text):
        value = match.group()
        if validate_iban(value):
            entity_type = "TR_IBAN" if compact_iban(value).startswith("TR") else "IBAN_OTHER"
            hits.append(DetectorHit(entity_type, match.start(), match.end(), 1.0))
    return hits


class IbanRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="IbanMod97Recognizer",
            supported_entities=["TR_IBAN", "IBAN_OTHER"],
            detector=detect_iban,
            language=language,
        )
