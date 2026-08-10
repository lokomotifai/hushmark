#!/usr/bin/env python3
"""Evaluate a local hushmark-tr checkpoint and emit the binding adoption verdict."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from hushmark_bench.dataset import load_dataset
from hushmark_bench.metrics import evaluate
from hushmark_bench.runner import enforce_l0_gate, verify_lock
from hushmark_bench.training import adoption_verdict, load_model_labels, sha256_file
from hushmark_core.config import Settings
from hushmark_core.engine import DetectionEngine
from hushmark_core.ner.base import NerSpan
from hushmark_core.ner.decode import decode_predictions

ROOT = Path(__file__).resolve().parents[2]


class CheckpointBackend:
    def __init__(
        self, checkpoint: Path, labels: dict[str, str], model_id: str, device: str
    ) -> None:
        self.checkpoint = checkpoint
        self._label_to_type = {label: entity_type for entity_type, label in labels.items()}
        self._model_id = model_id
        self._device = device
        self._model: Any | None = None
        self._weights = checkpoint / "pytorch_model.bin"
        self._sha256 = sha256_file(self._weights)

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_sha256(self) -> str:
        return self._sha256

    def load(self) -> None:
        if self._model is None:
            gliner_class = importlib.import_module("gliner").GLiNER
            self._model = (
                gliner_class.from_pretrained(
                    str(self.checkpoint), local_files_only=True, map_location="cpu"
                )
                .to(self._device)
                .eval()
            )

    def is_ready(self) -> bool:
        return self._model is not None

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        self.load()
        predictions = self._model.predict_entities(
            text, list(self._label_to_type), threshold=threshold
        )
        return decode_predictions(predictions, self._label_to_type)


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument(
        "--incumbent", type=Path, default=ROOT / "bench/reports/v0-baseline-core.json"
    )
    args = parser.parse_args()

    manifest_path = args.checkpoint / "training_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("checkpoint manifest must be an object")
    labels = load_model_labels(args.registry)
    backend = CheckpointBackend(args.checkpoint, labels, str(manifest["model_id"]), args.device)
    if backend.model_sha256 != manifest.get("weights_sha256"):
        raise ValueError("checkpoint weights do not match the training manifest")
    settings = Settings()
    engine = DetectionEngine(backend, settings.ner_threshold, settings.ner_thresholds)
    data_path = ROOT / "bench/data/hushmark-bench-v0.jsonl"
    lock_path = ROOT / "bench/data/hushmark-bench-v0.sha256"
    dataset_sha256 = verify_lock(data_path, lock_path)
    examples = load_dataset(data_path)
    if args.limit is not None:
        examples = examples[: args.limit]
    predictions: list[list[dict[str, object]]] = []
    started = time.perf_counter()
    for index, example in enumerate(examples, start=1):
        predictions.append([asdict(entity) for entity in engine.analyze(example["text"], "tr")])
        if index % 100 == 0:
            print(f"evaluated {index}/{len(examples)}", flush=True)
    strict = evaluate([example["entities"] for example in examples], predictions, mode="strict")
    partial = evaluate([example["entities"] for example in examples], predictions, mode="partial")
    if args.limit is None:
        enforce_l0_gate(strict)
    candidate: dict[str, Any] = {
        "schema_version": 1,
        "engine": "hushmark-tr-candidate",
        "backend": f"torch:{args.device}",
        "model_id": engine.model_id,
        "model_sha256": engine.model_sha256,
        "dataset": {
            "name": data_path.name,
            "examples": len(examples),
            "sha256": dataset_sha256,
        },
        "duration_seconds": time.perf_counter() - started,
        "strict": strict,
        "partial": partial,
    }
    incumbent = json.loads(args.incumbent.read_text(encoding="utf-8"))
    eligible = bool(manifest.get("adoption_eligible")) and args.limit is None
    verdict = adoption_verdict(candidate, cast(dict[str, Any], incumbent), eligible=eligible)
    report = {
        "schema_version": 1,
        "checkpoint": str(args.checkpoint),
        "training_manifest": manifest,
        "candidate": candidate,
        "incumbent": {
            "model_id": incumbent["model_id"],
            "model_sha256": incumbent["model_sha256"],
        },
        "verdict": verdict,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"adopt={str(verdict['adopt']).lower()} eligible={str(verdict['eligible']).lower()} "
        f"improvement={verdict['improvement']:.6f} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
