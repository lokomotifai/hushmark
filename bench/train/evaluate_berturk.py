#!/usr/bin/env python3
"""Compare a selected BERTurk span candidate with the adopted hushmark-tr model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from hushmark_bench.berturk_span import BerturkSpanModel
from hushmark_bench.checkpoint import CheckpointBackend
from hushmark_bench.dataset import load_dataset
from hushmark_bench.training import (
    adoption_verdict,
    load_model_labels,
    sha256_file,
    supplemental_adoption_verdict,
)
from hushmark_bench.validation import validate_ner_model, validate_ner_model_batched
from hushmark_core.ner.onnx_backend import OnnxNerBackend
from hushmark_core.ner.registry import load_model_spec

ROOT = Path(__file__).resolve().parents[2]
LEGACY_SHA256 = "6170b620faa349dbcbf2f2a973d5de20e35c6594e5626a2a589d20df5f67d642"
NEW_SHA256 = "72a231bb7766d502d6d7db9c6d6851291f9d20041e7189a55722224922eb0d11"
INCUMBENT_SHA256 = "a8f8bc87fdd4d4a92898513fd87eed9e7ccd2b6603ef1d1d5ce152e49192b6c2"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return cast(dict[str, Any], value)


def load_incumbent_legacy_report(path: Path) -> dict[str, Any]:
    """Load the adopted model's once-only locked report without re-running it."""

    if tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            member = archive.extractfile("ac1-final-verdict.json")
            if member is None:
                raise ValueError("AC-1 evidence archive has no final verdict")
            value = json.loads(member.read())
    else:
        value = load_json(path)
    if not isinstance(value, dict):
        raise ValueError("incumbent legacy report must be an object")
    candidate = value.get("candidate")
    report = candidate if isinstance(candidate, dict) else value
    if report.get("model_sha256") != INCUMBENT_SHA256:
        raise ValueError("incumbent legacy report is not for the adopted hushmark-tr weights")
    dataset = report.get("dataset")
    if not isinstance(dataset, Mapping) or dataset.get("sha256") != LEGACY_SHA256:
        raise ValueError("incumbent legacy report is not for the locked legacy dataset")
    return cast(dict[str, Any], report)


def verify_candidate(candidate_run: Path, legacy: Path, new: Path) -> dict[str, Any]:
    manifest = load_json(candidate_run / "training_manifest.json")
    if not (
        manifest.get("complete") is True
        and manifest.get("run_kind") == "full"
        and manifest.get("pilot_quality_pass") is True
    ):
        raise ValueError("candidate is not a complete, quality-passing full run")
    artifact_files = manifest.get("artifact_files")
    if not isinstance(artifact_files, Mapping) or not artifact_files:
        raise ValueError("candidate manifest has no artifact inventory")
    for relative, expected in artifact_files.items():
        if not isinstance(relative, str) or not isinstance(expected, Mapping):
            raise ValueError("candidate artifact inventory is malformed")
        artifact = candidate_run / "model" / relative
        if (
            not artifact.is_file()
            or artifact.stat().st_size != int(expected["size"])
            or sha256_file(artifact) != expected["sha256"]
        ):
            raise ValueError(f"candidate artifact failed verification: {relative}")

    config = load_json(candidate_run / "run_config.json")
    evaluation_suites = config.get("evaluation_suites")
    if not isinstance(evaluation_suites, Mapping):
        raise ValueError("candidate run has no locked evaluation inventory")
    approved = {
        "legacy_locked": (legacy, LEGACY_SHA256),
        "new_locked": (new, NEW_SHA256),
    }
    for name, (path, expected_sha256) in approved.items():
        suite = evaluation_suites.get(name)
        if not isinstance(suite, Mapping) or suite.get("sha256") != expected_sha256:
            raise ValueError(f"candidate did not declare the approved {name} suite")
        if sha256_file(path) != expected_sha256:
            raise ValueError(f"locked evaluation file failed verification: {path}")
    return manifest


def artifact_digest(manifest: Mapping[str, Any]) -> str:
    encoded = json.dumps(manifest["artifact_files"], sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def evaluate_candidate(
    model: BerturkSpanModel,
    examples: list[dict[str, Any]],
    labels: dict[str, str],
    *,
    threshold: float,
    batch_size: int,
    model_sha256: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    report = validate_ner_model_batched(
        model,
        examples,
        labels,
        threshold=threshold,
        batch_size=batch_size,
    )
    report.update(
        {
            "model_id": "hushmark-berturk-span-candidate",
            "model_sha256": model_sha256,
            "backend": f"torch:{model.device.type}",
            "duration_seconds": time.perf_counter() - started,
        }
    )
    return report


def evaluate_incumbent(
    checkpoint: Path,
    examples: list[dict[str, Any]],
    labels: dict[str, str],
    *,
    threshold: float,
    device: str,
    backend_name: str,
    registry: Path,
) -> dict[str, Any]:
    runtime: Any
    if backend_name == "onnx":
        spec = load_model_spec(registry, "hushmark-tr")
        onnx_backend = OnnxNerBackend(
            model_dir=checkpoint,
            spec=spec,
            onnx_model_file=spec.onnx_file,
        )

        class OnnxValidationAdapter:
            def predict_entities(
                self, text: str, model_labels: list[str], threshold: float
            ) -> list[dict[str, object]]:
                if set(model_labels) != set(labels.values()):
                    raise ValueError("incumbent label set does not match the closed taxonomy")
                return [
                    {
                        "label": labels[span.entity_type],
                        "start": span.start,
                        "end": span.end,
                        "score": span.confidence,
                    }
                    for span in onnx_backend.predict(text, threshold)
                ]

        runtime = OnnxValidationAdapter()
        model_sha256 = onnx_backend.model_sha256
        backend_metadata = {
            "backend": "onnx:cpu",
            "onnx_sha256": spec.onnx_sha256,
            "onnx_confidence_scale": spec.onnx_confidence_scale,
        }
    else:
        torch_backend = CheckpointBackend(checkpoint, labels, "hushmark-tr", device)
        runtime = torch_backend
        model_sha256 = torch_backend.model_sha256
        backend_metadata = {"backend": f"torch:{device}"}
    if model_sha256 != INCUMBENT_SHA256:
        raise ValueError("incumbent checkpoint does not match the adopted hushmark-tr weights")
    started = time.perf_counter()
    report = validate_ner_model(runtime, examples, labels, threshold=threshold)
    report.update(
        {
            "model_id": "hushmark-tr",
            "model_sha256": model_sha256,
            "duration_seconds": time.perf_counter() - started,
            **backend_metadata,
        }
    )
    return report


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "models/hushmark-tr")
    parser.add_argument(
        "--incumbent-legacy-report",
        type=Path,
        default=ROOT / "dist/ac1/hushmark-ac1-retry-evidence-20260810.tar",
    )
    parser.add_argument(
        "--legacy-dataset", type=Path, default=ROOT / "bench/data/hushmark-bench-v0.jsonl"
    )
    parser.add_argument(
        "--new-dataset",
        type=Path,
        default=ROOT
        / "dataset-prep/prepared/v1/tasks/gliner_hushmark/evaluation/splits/test_locked.jsonl",
    )
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--candidate-batch-size", type=int, default=32)
    parser.add_argument("--candidate-threshold", type=float, default=0.50)
    parser.add_argument("--incumbent-threshold", type=float, default=0.55)
    parser.add_argument("--incumbent-backend", choices=("onnx", "torch"), default="onnx")
    args = parser.parse_args()

    manifest = verify_candidate(args.candidate_run, args.legacy_dataset, args.new_dataset)
    labels = load_model_labels(args.registry)
    model = BerturkSpanModel.load_artifact(args.candidate_run / "model").to(args.device).eval()
    if set(model.label_names) != set(labels.values()):
        raise ValueError("candidate label set does not match the closed Hushmark taxonomy")
    digest = artifact_digest(manifest)
    legacy_examples = load_dataset(args.legacy_dataset)
    new_examples = load_dataset(args.new_dataset)

    print("evaluating candidate on locked legacy suite", flush=True)
    candidate_legacy = evaluate_candidate(
        model,
        legacy_examples,
        labels,
        threshold=args.candidate_threshold,
        batch_size=args.candidate_batch_size,
        model_sha256=digest,
    )
    incumbent_legacy = load_incumbent_legacy_report(args.incumbent_legacy_report)
    legacy_verdict = adoption_verdict(candidate_legacy, incumbent_legacy, eligible=True)

    print("evaluating candidate on locked new-data suite", flush=True)
    candidate_new = evaluate_candidate(
        model,
        new_examples,
        labels,
        threshold=args.candidate_threshold,
        batch_size=args.candidate_batch_size,
        model_sha256=digest,
    )
    del model

    print("evaluating incumbent on locked new-data suite", flush=True)
    incumbent_new = evaluate_incumbent(
        args.incumbent,
        new_examples,
        labels,
        threshold=args.incumbent_threshold,
        device=args.device,
        backend_name=args.incumbent_backend,
        registry=args.registry,
    )
    supported_types = sorted(
        {
            str(entity["type"])
            for example in new_examples
            for entity in example["entities"]
            if entity.get("type") in labels
        }
    )
    final_verdict = supplemental_adoption_verdict(
        candidate_new,
        incumbent_new,
        entity_types=supported_types,
        eligible=bool(legacy_verdict["adopt"]),
    )
    report = {
        "schema_version": 1,
        "candidate_run": str(args.candidate_run),
        "candidate_artifact_sha256": digest,
        "candidate_threshold": args.candidate_threshold,
        "incumbent_threshold": args.incumbent_threshold,
        "datasets": {
            "legacy": {
                "path": str(args.legacy_dataset),
                "examples": len(legacy_examples),
                "sha256": LEGACY_SHA256,
            },
            "new": {
                "path": str(args.new_dataset),
                "examples": len(new_examples),
                "sha256": NEW_SHA256,
                "supported_types": supported_types,
            },
        },
        "legacy": {
            "candidate": candidate_legacy,
            "incumbent": incumbent_legacy,
            "verdict": legacy_verdict,
        },
        "new": {
            "candidate": candidate_new,
            "incumbent": incumbent_new,
            "verdict": final_verdict,
        },
        "verdict": final_verdict,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"adopt={str(final_verdict['adopt']).lower()} "
        f"legacy_improvement={legacy_verdict['improvement']:.6f} "
        f"new_improvement={final_verdict['improvement']:.6f} report={args.report}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
