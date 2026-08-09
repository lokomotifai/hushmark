"""Turkish SGK registration-number pattern with explicit context scoring."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer

SGK_PATTERN = re.compile(r"(?<!\d)\d{13}(?!\d)")
SGK_CONTEXT = re.compile(r"\b(?:sgk|ssk|sicil|sosyal\s+güvenlik)\b", flags=re.IGNORECASE)


def validate_tr_sgk(value: str) -> bool:
    return len(value) == 13 and value.isascii() and value.isdigit()


def detect_tr_sgk(text: str) -> list[DetectorHit]:
    hits: list[DetectorHit] = []
    for match in SGK_PATTERN.finditer(text):
        if not validate_tr_sgk(match.group()):
            continue
        context_start = max(0, match.start() - 32)
        context_end = min(len(text), match.end() + 32)
        score = 0.88 if SGK_CONTEXT.search(text[context_start:context_end]) else 0.6
        hits.append(DetectorHit("TR_SGK", match.start(), match.end(), score))
    return hits


class SgkRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishSgkRecognizer",
            supported_entities=["TR_SGK"],
            detector=detect_tr_sgk,
            language=language,
        )
