"""Decode BIO/BIOES token-classification tags into the closed taxonomy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hushmark_core.ner.base import NerSpan
from hushmark_core.taxonomy_gen import TAXONOMY

_TAG_PREFIXES = frozenset({"B", "I", "E", "S"})
_CONTINUATION_PREFIXES = frozenset({"I", "E"})


@dataclass(frozen=True, slots=True)
class TokenPrediction:
    label: str
    score: float
    start: int
    end: int


def decode_bio_predictions(
    tokens: Sequence[TokenPrediction],
    label_to_type: Mapping[str, str],
) -> list[NerSpan]:
    spans: list[NerSpan] = []
    open_type: str | None = None
    open_base: str | None = None
    open_start = 0
    open_end = 0
    open_scores: list[float] = []

    def close_open() -> None:
        nonlocal open_type, open_base, open_scores
        if open_type is not None:
            confidence = sum(open_scores) / len(open_scores)
            spans.append(NerSpan(open_type, open_start, open_end, min(1.0, max(0.0, confidence))))
        open_type = None
        open_base = None
        open_scores = []

    for token in tokens:
        if not 0.0 <= token.score <= 1.0:
            raise ValueError("model emitted invalid confidence")
        if token.start == token.end:
            # Special tokens carry a zero-width offset mapping.
            continue
        if token.start < 0 or token.end < token.start:
            raise ValueError("model emitted invalid span offsets")
        if token.label == "O":
            close_open()
            continue
        prefix, separator, base_label = token.label.partition("-")
        if prefix not in _TAG_PREFIXES or not separator or not base_label:
            raise ValueError(f"model emitted an unknown tag: {token.label}")
        if base_label not in label_to_type:
            # Model labels outside the configured mapping are intentionally
            # dropped; the deterministic layer owns those entity types.
            close_open()
            continue
        entity_type = label_to_type[base_label]
        if entity_type not in TAXONOMY or TAXONOMY[entity_type]["layer"] != "ner":
            raise ValueError(f"model label maps outside the NER taxonomy: {entity_type}")
        continues_open = (
            prefix in _CONTINUATION_PREFIXES and open_base == base_label and token.start >= open_end
        )
        if continues_open:
            open_end = token.end
            open_scores.append(token.score)
            if prefix == "E":
                close_open()
            continue
        close_open()
        open_type = entity_type
        open_base = base_label
        open_start = token.start
        open_end = token.end
        open_scores = [token.score]
        if prefix in {"S", "E"}:
            # S is a complete single-token span; an orphan E (chunk boundary
            # artifact) is decoded leniently as a single-token span.
            close_open()
    close_open()
    return spans


def merge_chunk_spans(spans: Sequence[NerSpan]) -> list[NerSpan]:
    merged: list[NerSpan] = []
    for span in sorted(spans, key=lambda item: (item.entity_type, item.start, item.end)):
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.entity_type == span.entity_type
            and span.start < previous.end
        ):
            # Overlapping same-type fragments from stride overlap merge into
            # their union so a chunk boundary can never truncate an entity.
            merged[-1] = NerSpan(
                entity_type=previous.entity_type,
                start=previous.start,
                end=max(previous.end, span.end),
                confidence=max(previous.confidence, span.confidence),
            )
            continue
        merged.append(span)
    return sorted(merged, key=lambda item: (item.start, item.end, item.entity_type))
