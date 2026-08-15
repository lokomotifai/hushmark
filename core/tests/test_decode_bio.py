from __future__ import annotations

import pytest
from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode_bio import (
    TokenPrediction,
    decode_bio_predictions,
    merge_chunk_spans,
)

LABEL_TO_TYPE = {
    "identity.person_name": "PERSON",
    "healthcare.condition": "HEALTH",
    "healthcare.medication": "HEALTH",
}


def test_bioes_tokens_merge_into_single_span_with_mean_confidence() -> None:
    tokens = [
        TokenPrediction("B-identity.person_name", 0.9, 0, 4),
        TokenPrediction("I-identity.person_name", 0.7, 5, 11),
        TokenPrediction("E-identity.person_name", 0.8, 12, 18),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert spans == [NerSpan("PERSON", 0, 18, pytest.approx(0.8))]


def test_adjacent_b_tags_open_separate_spans() -> None:
    tokens = [
        TokenPrediction("B-identity.person_name", 0.9, 0, 4),
        TokenPrediction("B-identity.person_name", 0.8, 5, 9),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert [(span.start, span.end) for span in spans] == [(0, 4), (5, 9)]


def test_single_token_s_tag_closes_immediately() -> None:
    tokens = [
        TokenPrediction("S-healthcare.condition", 0.95, 3, 9),
        TokenPrediction("O", 0.99, 10, 14),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert spans == [NerSpan("HEALTH", 3, 9, 0.95)]


def test_many_model_labels_map_to_one_taxonomy_type() -> None:
    tokens = [
        TokenPrediction("S-healthcare.condition", 0.9, 0, 5),
        TokenPrediction("S-healthcare.medication", 0.9, 6, 12),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert [span.entity_type for span in spans] == ["HEALTH", "HEALTH"]


def test_unmapped_model_labels_are_dropped_silently() -> None:
    tokens = [
        TokenPrediction("B-identity.person_name", 0.9, 0, 4),
        TokenPrediction("B-contact.email", 0.9, 5, 15),
        TokenPrediction("E-contact.email", 0.9, 16, 20),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert spans == [NerSpan("PERSON", 0, 4, 0.9)]


def test_mapping_to_deterministic_layer_type_raises() -> None:
    with pytest.raises(ValueError, match="outside"):
        decode_bio_predictions(
            [TokenPrediction("B-national id", 0.9, 0, 4)],
            {"national id": "TR_TCKN"},
        )


def test_orphan_continuation_tags_open_lenient_spans() -> None:
    tokens = [
        TokenPrediction("I-identity.person_name", 0.9, 0, 4),
        TokenPrediction("E-identity.person_name", 0.7, 5, 9),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert spans == [NerSpan("PERSON", 0, 9, pytest.approx(0.8))]


def test_special_tokens_and_o_tags_are_skipped() -> None:
    tokens = [
        TokenPrediction("O", 1.0, 0, 0),
        TokenPrediction("B-identity.person_name", 0.9, 0, 4),
        TokenPrediction("O", 0.99, 5, 8),
        TokenPrediction("O", 1.0, 0, 0),
    ]
    spans = decode_bio_predictions(tokens, LABEL_TO_TYPE)
    assert spans == [NerSpan("PERSON", 0, 4, 0.9)]


def test_invalid_offsets_and_scores_raise() -> None:
    with pytest.raises(ValueError, match="invalid confidence"):
        decode_bio_predictions(
            [TokenPrediction("B-identity.person_name", 1.5, 0, 4)],
            LABEL_TO_TYPE,
        )
    with pytest.raises(ValueError, match="invalid span offsets"):
        decode_bio_predictions(
            [TokenPrediction("B-identity.person_name", 0.9, -1, 4)],
            LABEL_TO_TYPE,
        )
    with pytest.raises(ValueError, match="unknown tag"):
        decode_bio_predictions(
            [TokenPrediction("X-identity.person_name", 0.9, 0, 4)],
            LABEL_TO_TYPE,
        )


def test_merge_chunk_spans_dedupes_and_unions_overlaps() -> None:
    spans = [
        NerSpan("PERSON", 0, 10, 0.8),
        NerSpan("PERSON", 0, 10, 0.9),
        NerSpan("PERSON", 8, 20, 0.7),
        NerSpan("HEALTH", 5, 9, 0.6),
        NerSpan("PERSON", 25, 30, 0.5),
    ]
    merged = merge_chunk_spans(spans)
    assert merged == [
        NerSpan("PERSON", 0, 20, 0.9),
        NerSpan("HEALTH", 5, 9, 0.6),
        NerSpan("PERSON", 25, 30, 0.5),
    ]
