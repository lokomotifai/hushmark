"""Turkish mobile and landline phone-number validation."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer
from hushmark_core.recognizers.digits import ascii_digit

PHONE_PATTERN = re.compile(
    r"(?<!\d)\+?(?:\d[ .()-]*){9,13}\d(?!\d)",
)
MOBILE_PREFIXES = {f"5{second}{third}" for second in range(10) for third in range(10)}
LANDLINE_PREFIXES = {
    "212",
    "216",
    "222",
    "224",
    "226",
    "228",
    "232",
    "236",
    "242",
    "246",
    "248",
    "252",
    "256",
    "258",
    "262",
    "264",
    "266",
    "272",
    "274",
    "276",
    "282",
    "284",
    "286",
    "288",
    "312",
    "318",
    "322",
    "324",
    "326",
    "328",
    "332",
    "338",
    "342",
    "344",
    "346",
    "348",
    "352",
    "354",
    "356",
    "358",
    "362",
    "364",
    "366",
    "368",
    "370",
    "372",
    "374",
    "376",
    "378",
    "380",
    "382",
    "384",
    "386",
    "388",
    "412",
    "414",
    "416",
    "422",
    "424",
    "426",
    "428",
    "432",
    "434",
    "436",
    "438",
    "442",
    "446",
    "452",
    "454",
    "456",
    "458",
    "462",
    "464",
    "466",
    "472",
    "474",
    "476",
    "478",
    "482",
    "484",
    "486",
    "488",
}


def compact_phone(value: str) -> str:
    return "".join(digit for char in value if (digit := ascii_digit(char)) is not None)


def validate_tr_phone(value: str) -> bool:
    digits = compact_phone(value)
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("90") and (value.lstrip().startswith("+90") or len(digits) == 12):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10:
        return False
    return digits[:3] in MOBILE_PREFIXES or digits[:3] in LANDLINE_PREFIXES


def detect_tr_phone(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("TR_PHONE", match.start(), match.end(), 0.9)
        for match in PHONE_PATTERN.finditer(text)
        if validate_tr_phone(match.group())
    ]


class PhoneRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishPhoneRecognizer",
            supported_entities=["TR_PHONE"],
            detector=detect_tr_phone,
            language=language,
        )
