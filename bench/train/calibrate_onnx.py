#!/usr/bin/env python3
"""Calibrate an ONNX checkpoint on development data with one inference pass."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from hushmark_bench.dataset import load_dataset
from hushmark_bench.training import load_model_labels
from hushmark_bench.validation import validate_ner_model_batched, validate_ner_thresholds

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_THRESHOLDS = (
    0.001,
    0.0025,
    0.005,
    0.01,
    0.02,
    0.04,
    0.08,
    0.12,
    0.16,
    0.2,
    0.275,
    0.4,
    0.5,
    0.55,
)


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--validation-data", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument("--onnx-model-file", default="model.onnx")
    parser.add_argument("--threshold", action="append", type=float, dest="thresholds")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()

    from gliner import GLiNER  # type: ignore[import-untyped]

    model_file = args.checkpoint / args.onnx_model_file
    if not model_file.is_file():
        raise FileNotFoundError(f"ONNX model is missing: {model_file}")
    examples = load_dataset(args.validation_data)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("limit must be positive")
        examples = examples[: args.limit]
    model = GLiNER.from_pretrained(
        str(args.checkpoint),
        local_files_only=True,
        load_onnx_model=True,
        onnx_model_file=str(model_file),
    )
    thresholds = args.thresholds or list(DEFAULT_THRESHOLDS)
    labels = load_model_labels(args.registry)
    if args.batch_size > 1:
        if len(thresholds) != 1:
            raise ValueError("batched validation requires exactly one threshold")
        reports = [
            validate_ner_model_batched(
                model,
                examples,
                labels,
                threshold=thresholds[0],
                batch_size=args.batch_size,
            )
        ]
    else:
        reports = validate_ner_thresholds(
            model,
            examples,
            labels,
            thresholds=thresholds,
        )
    best = max(reports, key=lambda report: float(report["ner_macro_f1"]))
    payload = {
        "schema_version": 1,
        "checkpoint": str(args.checkpoint),
        "onnx_model_file": args.onnx_model_file,
        "reports": reports,
        "best": best,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"best_threshold={best['threshold']} "
        f"ner_macro_f1={best['ner_macro_f1']:.6f} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
