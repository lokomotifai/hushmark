"""Turkish vehicle-registration plate detection."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

PLATE_PATTERN = re.compile(
    r"(?<![A-ZÇĞİÖŞÜ0-9])(?:0?[1-9]|[1-7][0-9]|8[01])[ -]*"
    r"[A-ZÇĞİÖŞÜ]{1,3}[ -]*\d{2,4}(?![A-ZÇĞİÖŞÜ0-9])",
    flags=re.IGNORECASE,
)


def validate_tr_plate(value: str) -> bool:
    match = PLATE_PATTERN.fullmatch(value)
    if match is None:
        return False
    province_text = re.match(r"\d{1,2}", value)
    return province_text is not None and 1 <= int(province_text.group()) <= 81


def detect_tr_plate(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("TR_PLATE", match.start(), match.end(), 0.92)
        for match in PLATE_PATTERN.finditer(text)
        if validate_tr_plate(match.group())
    ]


class PlateRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishPlateRecognizer",
            supported_entities=["TR_PLATE"],
            detector=detect_tr_plate,
            language=language,
        )
