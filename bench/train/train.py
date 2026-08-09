#!/usr/bin/env python3
"""Fine-tune the pinned GLiNER model; smoke mode is offline, CPU-only, and bounded."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any

from hushmark_bench.training import (
    json_lines,
    load_model_labels,
    load_prepared,
    sha256_file,
    smoke_records,
)

ROOT = Path(__file__).resolve().parents[2]


def train(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    import torch
    from gliner import GLiNER
    from torch.utils.data import DataLoader

    started = time.perf_counter()
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    labels = load_model_labels(args.registry)
    if args.smoke:
        records = (
            smoke_records(args.seed, labels) if args.data is None else load_prepared(args.data)
        )
        if len(records) < 200:
            raise ValueError("smoke training requires at least 200 prepared examples")
        records = random.Random(args.seed).sample(records, 200)
        epochs = 1
        batch_size = args.batch_size or 8
    else:
        if not args.authorized_full_run:
            raise PermissionError(
                "full training requires --authorized-full-run after AC-1 approval"
            )
        if args.data is None:
            raise ValueError("full training requires --data")
        records = load_prepared(args.data)
        if any(record.get("source") == "hushmark-bench-v0" for record in records):
            raise ValueError("full training data must not contain the evaluation benchmark")
        epochs = args.epochs
        batch_size = args.batch_size or 16

    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    if not (args.model_dir / "pytorch_model.bin").is_file():
        raise FileNotFoundError(f"pinned base model is missing: {args.model_dir}")

    model = GLiNER.from_pretrained(str(args.model_dir), local_files_only=True, map_location="cpu")
    model.to("cpu" if args.smoke else args.device)
    if args.smoke:
        model.freeze_component("text_encoder")
    model.train()
    collator = model._create_data_collator()
    generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        records,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=collator,
        num_workers=0,
        generator=generator,
    )
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if not parameters:
        raise RuntimeError("training configuration has no trainable parameters")
    optimizer = torch.optim.AdamW(parameters, lr=args.learning_rate, weight_decay=0.01)
    losses: list[float] = []
    for epoch in range(epochs):
        for batch_index, batch in enumerate(loader, start=1):
            batch = {
                key: value.to("cpu" if args.smoke else args.device)
                if isinstance(value, torch.Tensor)
                else value
                for key, value in batch.items()
            }
            optimizer.zero_grad(set_to_none=True)
            output = model(**batch, reduction="mean", masking="none")
            if output.loss is None or not torch.isfinite(output.loss):
                raise RuntimeError("GLiNER returned a missing or non-finite loss")
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 1.0)
            optimizer.step()
            losses.append(float(output.loss.detach()))
            print(
                f"epoch={epoch + 1}/{epochs} batch={batch_index}/{len(loader)} "
                f"loss={losses[-1]:.6f}",
                flush=True,
            )

    args.output.mkdir(parents=True)
    model.eval()
    model.save_pretrained(args.output, safe_serialization=False)
    elapsed = time.perf_counter() - started
    weights = args.output / "pytorch_model.bin"
    manifest = {
        "schema_version": 1,
        "model_id": "hushmark-tr-smoke" if args.smoke else "hushmark-tr",
        "base_model": "gliner_multi_pii-v1",
        "smoke": args.smoke,
        "adoption_eligible": not args.smoke,
        "examples": len(records),
        "epochs": epochs,
        "batch_size": batch_size,
        "seed": args.seed,
        "device": "cpu" if args.smoke else args.device,
        "frozen_components": ["text_encoder"] if args.smoke else [],
        "learning_rate": args.learning_rate,
        "mean_loss": sum(losses) / len(losses),
        "final_loss": losses[-1],
        "elapsed_seconds": elapsed,
        "weights_sha256": sha256_file(weights),
        "training_records_sha256": hashlib.sha256(json_lines(records).encode()).hexdigest(),
        "training_sources": sorted({str(record.get("source", "unknown")) for record in records}),
    }
    (args.output / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.smoke and elapsed >= 600:
        raise RuntimeError(f"CPU smoke training exceeded 10 minutes: {elapsed:.1f}s")
    print(json.dumps(manifest, sort_keys=True))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--authorized-full-run", action="store_true")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--model-dir", type=Path, default=ROOT / "models/gliner_multi_pii-v1")
    parser.add_argument("--registry", type=Path, default=ROOT / "core/models.yaml")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "bench/train/outputs/smoke-checkpoint"
    )
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cuda")
    args = parser.parse_args()
    if not args.smoke and not args.authorized_full_run:
        parser.error("choose --smoke or provide --authorized-full-run after AC-1 approval")
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
