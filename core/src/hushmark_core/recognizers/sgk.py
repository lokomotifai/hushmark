"""Turkish SGK registration-number pattern with explicit context scoring."""

from __future__ import annotations

import re

from hushmark_core.recognizers.base import DetectorHit, ValidatorRecognizer
from hushmark_core.recognizers.digits import iter_digit_candidates

SGK_CONTEXT = re.compile(r"\b(?:sgk|ssk|sicil|sosyal\s+güvenlik)\b", flags=re.IGNORECASE)


def validate_tr_sgk(value: str) -> bool:
    return len(value) == 13 and value.isascii() and value.isdigit()


def detect_tr_sgk(text: str) -> list[DetectorHit]:
    hits: list[DetectorHit] = []
    for start, end, normalized in iter_digit_candidates(text, 13):
        if not validate_tr_sgk(normalized):
            continue
        context_start = max(0, start - 32)
        context_end = min(len(text), end + 32)
        score = 0.88 if SGK_CONTEXT.search(text[context_start:context_end]) else 0.6
        hits.append(DetectorHit("TR_SGK", start, end, score))
    return hits


class SgkRecognizer(ValidatorRecognizer):
    def __init__(self, language: str) -> None:
        super().__init__(
            name="TurkishSgkRecognizer",
            supported_entities=["TR_SGK"],
            detector=detect_tr_sgk,
            language=language,
        )
