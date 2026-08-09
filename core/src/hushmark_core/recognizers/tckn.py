"""Turkish Republic identity-number validation."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

TCKN_PATTERN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")


def validate_tckn(value: str) -> bool:
    """Validate all eleven digits with both official checksum equations."""

    if len(value) != 11 or not value.isascii() or not value.isdigit() or value[0] == "0":
        return False
    digits = [int(char) for char in value]
    tenth = (7 * sum(digits[0:9:2]) - sum(digits[1:8:2])) % 10
    eleventh = sum(digits[:10]) % 10
    return digits[9] == tenth and digits[10] == eleventh


def detect_tckn(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("TR_TCKN", match.start(), match.end(), 1.0)
        for match in TCKN_PATTERN.finditer(text)
        if validate_tckn(match.group())
    ]


class TcknRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishTcknRecognizer",
            supported_entities=["TR_TCKN"],
            detector=detect_tckn,
            language=language,
        )
