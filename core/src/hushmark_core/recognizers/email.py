"""Pragmatic email-address recognition."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

EMAIL_PATTERN = re.compile(
    r"(?<![A-Z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}"
    r"(?![A-Z0-9-])",
    flags=re.IGNORECASE | re.ASCII,
)


def validate_email(value: str) -> bool:
    if len(value) > 254 or EMAIL_PATTERN.fullmatch(value) is None:
        return False
    local, _, domain = value.rpartition("@")
    return len(local) <= 64 and ".." not in local and ".." not in domain


def detect_email(text: str) -> list[DetectorHit]:
    return [
        DetectorHit("EMAIL", match.start(), match.end(), 0.95)
        for match in EMAIL_PATTERN.finditer(text)
        if validate_email(match.group())
    ]


class EmailRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="PragmaticEmailRecognizer",
            supported_entities=["EMAIL"],
            detector=detect_email,
            language=language,
        )
