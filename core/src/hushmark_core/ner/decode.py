"""Decode GLiNER dictionary predictions into the closed taxonomy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from hushmark_core.ner.base import NerSpan
from hushmark_core.taxonomy_gen import TAXONOMY


def decode_predictions(
    predictions: Sequence[Mapping[str, object]],
    label_to_type: Mapping[str, str],
) -> list[NerSpan]:
    spans: list[NerSpan] = []
    for prediction in predictions:
        label = prediction.get("label")
        start = prediction.get("start")
        end = prediction.get("end")
        score = prediction.get("score")
        if not isinstance(label, str) or label not in label_to_type:
            continue
        entity_type = label_to_type[label]
        if entity_type not in TAXONOMY or TAXONOMY[entity_type]["layer"] != "ner":
            raise ValueError(f"model label maps outside the NER taxonomy: {entity_type}")
        if not isinstance(start, int) or not isinstance(end, int) or not start < end:
            raise ValueError("model emitted invalid span offsets")
        if not isinstance(score, int | float) or not 0.0 <= float(score) <= 1.0:
            raise ValueError("model emitted invalid confidence")
        spans.append(NerSpan(entity_type, start, end, float(score)))
    return spans
