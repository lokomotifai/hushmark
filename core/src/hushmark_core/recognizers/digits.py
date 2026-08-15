"""Unicode-aware digit candidate extraction with original offset preservation."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator

SEPARATORS = frozenset(".-/\u200b\u200c\u200d\u2060")


def iter_digit_candidates(text: str, length: int) -> Iterator[tuple[int, int, str]]:
    """Yield fixed-length decimal digit sequences while tolerating common visual separators."""

    for start, char in enumerate(text):
        first = ascii_digit(char)
        if first is None or has_preceding_digit(text, start):
            continue
        digits = [first]
        cursor = start + 1
        end = cursor
        while cursor < len(text) and len(digits) < length:
            candidate = ascii_digit(text[cursor])
            if candidate is not None:
                digits.append(candidate)
                cursor += 1
                end = cursor
                continue
            if is_separator(text[cursor]):
                cursor += 1
                continue
            break
        if len(digits) != length or has_following_digit(text, end):
            continue
        yield start, end, "".join(digits)


def ascii_digit(char: str) -> str | None:
    try:
        return str(unicodedata.decimal(char))
    except (TypeError, ValueError):
        return None


def is_separator(char: str) -> bool:
    return char.isspace() or char in SEPARATORS


def has_preceding_digit(text: str, start: int) -> bool:
    cursor = start - 1
    while cursor >= 0 and is_separator(text[cursor]):
        cursor -= 1
    return cursor >= 0 and ascii_digit(text[cursor]) is not None


def has_following_digit(text: str, end: int) -> bool:
    cursor = end
    while cursor < len(text) and is_separator(text[cursor]):
        cursor += 1
    return cursor < len(text) and ascii_digit(text[cursor]) is not None
