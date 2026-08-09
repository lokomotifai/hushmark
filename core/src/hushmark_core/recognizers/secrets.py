"""Credential and private-key detection with entropy and structural checks."""

from __future__ import annotations

import math
import re
from collections import Counter

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

API_KEY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})(?![A-Za-z0-9_])"
)
JWT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?![A-Za-z0-9_-])"
)
PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+"
    r"[A-Za-z0-9+/=\r\n]{16,}\s+"
    r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    flags=re.MULTILINE,
)


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def validate_api_key(value: str) -> bool:
    return API_KEY_PATTERN.fullmatch(value) is not None and shannon_entropy(value) >= 3.5


def validate_jwt(value: str) -> bool:
    return JWT_PATTERN.fullmatch(value) is not None


def validate_private_key(value: str) -> bool:
    match = PRIVATE_KEY_PATTERN.fullmatch(value)
    if match is None:
        return False
    begin_label = re.search(r"BEGIN ([A-Z ]*PRIVATE KEY)", value)
    end_label = re.search(r"END ([A-Z ]*PRIVATE KEY)", value)
    return (
        begin_label is not None
        and end_label is not None
        and begin_label.group(1) == end_label.group(1)
    )


def detect_secrets(text: str) -> list[DetectorHit]:
    hits = [
        DetectorHit("SECRET_API_KEY", match.start(), match.end(), 1.0)
        for match in API_KEY_PATTERN.finditer(text)
        if validate_api_key(match.group())
    ]
    hits.extend(
        DetectorHit("SECRET_JWT", match.start(), match.end(), 1.0)
        for match in JWT_PATTERN.finditer(text)
        if validate_jwt(match.group())
    )
    hits.extend(
        DetectorHit("SECRET_PRIVATE_KEY", match.start(), match.end(), 1.0)
        for match in PRIVATE_KEY_PATTERN.finditer(text)
        if validate_private_key(match.group())
    )
    return hits


class SecretsRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="CredentialSecretsRecognizer",
            supported_entities=["SECRET_API_KEY", "SECRET_JWT", "SECRET_PRIVATE_KEY"],
            detector=detect_secrets,
            language=language,
        )
