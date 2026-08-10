"""NER-only development evaluation for checkpoint selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from hushmark_core.ner.decode import decode_predictions

from hushmark_bench.metrics import evaluate
from hushmark_bench.training import NER_TYPES, ner_macro_f1


class PredictingModel(Protocol):
    def predict_entities(
        self,
        text: str,
        labels: list[str],
        threshold: float,
    ) -> Sequence[Mapping[str, object]]: ...


class BatchPredictingModel(Protocol):
    def inference(
        self,
        texts: list[str],
        labels: list[str],
        *,
        threshold: float,
        batch_size: int,
    ) -> Sequence[Sequence[Mapping[str, object]]]: ...


def validate_ner_model(
    model: PredictingModel,
    examples: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str],
    *,
    threshold: float,
) -> dict[str, Any]:
    """Evaluate only NER-owned types without allowing deterministic L0 spans to mask failure."""

    label_to_type = {label: entity_type for entity_type, label in labels.items()}
    gold_documents: list[list[dict[str, Any]]] = []
    predicted_documents: list[list[dict[str, Any]]] = []
    for example in examples:
        text = example.get("text")
        entities = example.get("entities")
        if not isinstance(text, str) or not isinstance(entities, list):
            raise ValueError("development example requires text and entities")
        gold_documents.append(
            [
                dict(entity)
                for entity in entities
                if isinstance(entity, Mapping) and entity.get("type") in NER_TYPES
            ]
        )
        raw_predictions = model.predict_entities(text, list(label_to_type), threshold=threshold)
        predicted_documents.append(
            [
                {
                    "type": span.entity_type,
                    "start": span.start,
                    "end": span.end,
                    "confidence": span.confidence,
                }
                for span in decode_predictions(raw_predictions, label_to_type)
            ]
        )
    result = {
        "schema_version": 1,
        "examples": len(examples),
        "threshold": threshold,
        "strict": evaluate(gold_documents, predicted_documents, mode="strict"),
    }
    macro_f1, _ = ner_macro_f1(result)
    result["ner_macro_f1"] = macro_f1
    return result


def validate_ner_model_batched(
    model: BatchPredictingModel,
    examples: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str],
    *,
    threshold: float,
    batch_size: int,
) -> dict[str, Any]:
    """Evaluate one threshold through GLiNER's supported batched inference API."""

    if batch_size < 1 or not 0.0 <= threshold <= 1.0:
        raise ValueError("batch size or validation threshold is invalid")
    label_to_type = {label: entity_type for entity_type, label in labels.items()}
    texts: list[str] = []
    gold_documents: list[list[dict[str, Any]]] = []
    for example in examples:
        text = example.get("text")
        entities = example.get("entities")
        if not isinstance(text, str) or not isinstance(entities, list):
            raise ValueError("development example requires text and entities")
        texts.append(text)
        gold_documents.append(
            [
                dict(entity)
                for entity in entities
                if isinstance(entity, Mapping) and entity.get("type") in NER_TYPES
            ]
        )
    raw_documents = model.inference(
        texts,
        list(label_to_type),
        threshold=threshold,
        batch_size=batch_size,
    )
    if len(raw_documents) != len(examples):
        raise ValueError("batched model returned the wrong number of documents")
    predicted_documents = [
        [
            {
                "type": span.entity_type,
                "start": span.start,
                "end": span.end,
                "confidence": span.confidence,
            }
            for span in decode_predictions(raw_predictions, label_to_type)
        ]
        for raw_predictions in raw_documents
    ]
    result = {
        "schema_version": 1,
        "examples": len(examples),
        "threshold": threshold,
        "batch_size": batch_size,
        "strict": evaluate(gold_documents, predicted_documents, mode="strict"),
    }
    macro_f1, _ = ner_macro_f1(result)
    result["ner_macro_f1"] = macro_f1
    return result


def validate_ner_thresholds(
    model: PredictingModel,
    examples: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str],
    *,
    thresholds: Sequence[float],
) -> list[dict[str, Any]]:
    """Evaluate several thresholds from one low-threshold inference pass per example."""

    ordered_thresholds = sorted({float(threshold) for threshold in thresholds})
    if not ordered_thresholds or ordered_thresholds[0] < 0.0 or ordered_thresholds[-1] > 1.0:
        raise ValueError("validation thresholds must be a non-empty subset of [0, 1]")

    label_to_type = {label: entity_type for entity_type, label in labels.items()}
    gold_documents: list[list[dict[str, Any]]] = []
    scored_documents: list[list[dict[str, Any]]] = []
    for example in examples:
        text = example.get("text")
        entities = example.get("entities")
        if not isinstance(text, str) or not isinstance(entities, list):
            raise ValueError("development example requires text and entities")
        gold_documents.append(
            [
                dict(entity)
                for entity in entities
                if isinstance(entity, Mapping) and entity.get("type") in NER_TYPES
            ]
        )
        raw_predictions = model.predict_entities(
            text,
            list(label_to_type),
            threshold=ordered_thresholds[0],
        )
        scored_documents.append(
            [
                {
                    "type": span.entity_type,
                    "start": span.start,
                    "end": span.end,
                    "confidence": span.confidence,
                }
                for span in decode_predictions(raw_predictions, label_to_type)
            ]
        )

    reports: list[dict[str, Any]] = []
    for threshold in ordered_thresholds:
        predicted_documents = [
            [span for span in document if float(span["confidence"]) >= threshold]
            for document in scored_documents
        ]
        report: dict[str, Any] = {
            "schema_version": 1,
            "examples": len(examples),
            "inference_threshold": ordered_thresholds[0],
            "threshold": threshold,
            "strict": evaluate(gold_documents, predicted_documents, mode="strict"),
        }
        macro_f1, _ = ner_macro_f1(report)
        report["ner_macro_f1"] = macro_f1
        reports.append(report)
    return reports


def validation_rank(report: Mapping[str, Any]) -> tuple[int, float, float]:
    """Prefer a passing no-regression verdict, then macro-F1 and worst regression margin."""

    verdict = report.get("verdict")
    if not isinstance(verdict, Mapping):
        raise ValueError("validation report has no verdict")
    regressions = verdict.get("per_type_regressions")
    if not isinstance(regressions, Mapping):
        raise ValueError("validation verdict has invalid regressions")
    worst_regression = max((float(value) for value in regressions.values()), default=0.0)
    return (
        int(bool(verdict.get("technical_pass"))),
        float(verdict["candidate_ner_macro_f1"]),
        -worst_regression,
    )
