#!/usr/bin/env python3
"""Compare candidate and incumbent on the untouched new-data holdout."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, cast

from hushmark_bench.checkpoint import CheckpointBackend
from hushmark_bench.dataset import load_dataset
from hushmark_bench.training import (
    load_model_labels,
    sha256_file,
    supplemental_adoption_verdict,
)
from hushmark_bench.validation import validate_ner_model

ROOT = Path(__file__).resolve().parents[2]


def evaluate_checkpoint(
    checkpoint: Path,
    *,
    model_id: str,
    examples: list[dict[str, Any]],
    labels: dict[str, str],
    threshold: float,
    device: str,
) -> dict[str, Any]:
    backend = CheckpointBackend(checkpoint, labels, model_id, device)
    started = time.perf_counter()
    report = validate_ner_model(backend, examples, labels, threshold=threshold)
    report.update(
        {
            "model_id": backend.model_id,
            "model_sha256": backend.model_sha256,
            "backend": f"torch:{device}",
            "duration_seconds": time.perf_counter() - started,
        }
    )
    return report


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "models/hushmark-tr")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--legacy-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=0.55)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    args = parser.parse_args()

    actual_dataset_sha256 = sha256_file(args.dataset)
    if actual_dataset_sha256 != args.dataset_sha256:
        raise ValueError("new holdout does not match its approved SHA-256")
    manifest_path = args.candidate / "training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("candidate training manifest must be an object")
    candidate_weights_sha256 = sha256_file(args.candidate / "pytorch_model.bin")
    if candidate_weights_sha256 != manifest.get("weights_sha256"):
        raise ValueError("candidate weights do not match the training manifest")
    legacy = json.loads(args.legacy_report.read_text(encoding="utf-8"))
    legacy_verdict = legacy.get("verdict") if isinstance(legacy, dict) else None
    if not isinstance(legacy_verdict, dict):
        raise ValueError("legacy report has no verdict")

    examples = load_dataset(args.dataset)
    labels = load_model_labels(args.registry)
    supported_types = sorted(
        {
            str(entity["type"])
            for example in examples
            for entity in example["entities"]
            if entity.get("type") in labels
        }
    )
    candidate = evaluate_checkpoint(
        args.candidate,
        model_id=str(manifest["model_id"]),
        examples=examples,
        labels=labels,
        threshold=args.threshold,
        device=args.device,
    )
    incumbent = evaluate_checkpoint(
        args.incumbent,
        model_id="hushmark-tr-incumbent",
        examples=examples,
        labels=labels,
        threshold=args.threshold,
        device=args.device,
    )
    verdict = supplemental_adoption_verdict(
        candidate,
        incumbent,
        entity_types=supported_types,
        eligible=bool(legacy_verdict.get("adopt")),
    )
    report = {
        "schema_version": 1,
        "dataset": {
            "name": args.dataset.name,
            "examples": len(examples),
            "sha256": actual_dataset_sha256,
            "supported_types": supported_types,
        },
        "candidate": candidate,
        "incumbent": incumbent,
        "legacy_verdict": cast(dict[str, Any], legacy_verdict),
        "verdict": verdict,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"adopt={str(verdict['adopt']).lower()} "
        f"improvement={verdict['improvement']:.6f} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
