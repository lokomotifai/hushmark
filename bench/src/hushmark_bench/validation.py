"""NER-only development evaluation for checkpoint selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from hushmark_core.ner.decode import decode_predictions

from hushmark_bench.metrics import Counts, evaluate
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
        "partial": evaluate(gold_documents, predicted_documents, mode="partial"),
    }
    supported_types = sorted(
        entity_type
        for entity_type, metrics in result["strict"]["per_type"].items()
        if int(metrics["support"]) > 0
    )
    result["supported_types"] = supported_types
    result["ner_macro_f1"] = float(result["strict"]["macro"]["f1"])
    empty_gold_predictions = [
        len(predicted)
        for gold, predicted in zip(gold_documents, predicted_documents, strict=True)
        if not gold
    ]
    result["empty_gold"] = {
        "documents": len(empty_gold_predictions),
        "documents_with_false_positives": sum(count > 0 for count in empty_gold_predictions),
        "false_positive_spans": sum(empty_gold_predictions),
    }
    return result


def combine_validation_reports(
    reports: Mapping[str, Mapping[str, Any]], *, threshold: float
) -> dict[str, Any]:
    """Combine disjoint validation-suite counts without repeating model inference."""

    if not reports:
        raise ValueError("at least one validation suite is required")
    totals: dict[str, list[int]] = {}
    examples = 0
    for name, report in reports.items():
        if not name or float(report.get("threshold", -1)) != threshold:
            raise ValueError("validation suite threshold mismatch")
        examples += int(report.get("examples", 0))
        strict = report.get("strict")
        per_type = strict.get("per_type") if isinstance(strict, Mapping) else None
        if not isinstance(per_type, Mapping):
            raise ValueError("validation suite has invalid strict metrics")
        for entity_type, metrics in per_type.items():
            if not isinstance(metrics, Mapping):
                raise ValueError("validation suite has invalid per-type metrics")
            aggregate = totals.setdefault(str(entity_type), [0, 0, 0, 0])
            for index, field in enumerate(
                ("true_positive", "false_positive", "false_negative", "support")
            ):
                aggregate[index] += int(metrics.get(field, 0))

    per_type = {
        entity_type: Counts(*values).to_dict() for entity_type, values in sorted(totals.items())
    }
    supported = [metrics for metrics in per_type.values() if int(metrics["support"]) > 0]
    macro = {
        metric: sum(float(values[metric]) for values in supported) / len(supported)
        if supported
        else 0.0
        for metric in ("precision", "recall", "f1")
    }
    aggregate = [sum(values[index] for values in totals.values()) for index in range(4)]
    result: dict[str, Any] = {
        "schema_version": 1,
        "examples": examples,
        "threshold": threshold,
        "strict": {
            "mode": "strict",
            "per_type": per_type,
            "macro": macro,
            "micro": Counts(*aggregate).to_dict(),
        },
        "supported_types": sorted(
            entity_type for entity_type, metrics in per_type.items() if int(metrics["support"]) > 0
        ),
        "suites": dict(reports),
    }
    macro_f1, _ = ner_macro_f1(result)
    result["ner_macro_f1"] = macro_f1
    return result


def validate_ner_suites(
    model: PredictingModel,
    suites: Mapping[str, Sequence[Mapping[str, Any]]],
    labels: Mapping[str, str],
    *,
    threshold: float,
) -> dict[str, Any]:
    """Evaluate named suites once each and aggregate their exact span counts."""

    reports = {
        name: validate_ner_model(model, examples, labels, threshold=threshold)
        for name, examples in suites.items()
    }
    return combine_validation_reports(reports, threshold=threshold)


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
    empty_gold_predictions = [
        len(predicted)
        for gold, predicted in zip(gold_documents, predicted_documents, strict=True)
        if not gold
    ]
    result["empty_gold"] = {
        "documents": len(empty_gold_predictions),
        "documents_with_false_positives": sum(count > 0 for count in empty_gold_predictions),
        "false_positive_spans": sum(empty_gold_predictions),
    }
    # A named supplemental suite may intentionally cover only a subset of the
    # closed taxonomy. The combined multi-suite report still enforces support
    # for every NER type through ``combine_validation_reports``.
    result["ner_macro_f1"] = float(result["strict"]["macro"]["f1"])
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
