"""Turkish tax-identification-number validation."""

from __future__ import annotations

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer
from hushmark_core.recognizers.digits import iter_digit_candidates


def calculate_vkn_checksum(first_nine: str) -> int:
    """Calculate the tenth VKN digit using the modulus-10/9 transform."""

    if len(first_nine) != 9 or not first_nine.isascii() or not first_nine.isdigit():
        raise ValueError("VKN checksum input must contain exactly nine ASCII digits")
    total = 0
    for index, char in enumerate(first_nine):
        shifted = (int(char) + 9 - index) % 10
        contribution = (shifted * (2 ** (9 - index))) % 9
        if shifted != 0 and contribution == 0:
            contribution = 9
        total += contribution
    return (10 - total % 10) % 10


def validate_vkn(value: str) -> bool:
    if len(value) != 10 or not value.isascii() or not value.isdigit():
        return False
    return int(value[-1]) == calculate_vkn_checksum(value[:9])


def detect_vkn(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("TR_VKN", start, end, 1.0)
        for start, end, normalized in iter_digit_candidates(text, 10)
        if validate_vkn(normalized)
    ]


class VknRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishVknRecognizer",
            supported_entities=["TR_VKN"],
            detector=detect_vkn,
            language=language,
        )
