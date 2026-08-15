"""Turkish Republic identity-number validation."""

from __future__ import annotations

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer
from hushmark_core.recognizers.digits import iter_digit_candidates


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
        DetectorHit("TR_TCKN", start, end, 1.0)
        for start, end, normalized in iter_digit_candidates(text, 11)
        if validate_tckn(normalized)
    ]


class TcknRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishTcknRecognizer",
            supported_entities=["TR_TCKN"],
            detector=detect_tckn,
            language=language,
        )
