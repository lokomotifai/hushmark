#!/usr/bin/env python3
"""Export a locally installed GLiNER model when the installed revision supports it."""

from __future__ import annotations

import argparse
from hashlib import file_digest
from pathlib import Path

from gliner import GLiNER
from hushmark_core.ner.registry import load_model_spec

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", default="hushmark-tr")
    parser.add_argument("--output", default="model.onnx")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    model_dir = ROOT / "models" / args.model_id
    spec = load_model_spec(ROOT / "core" / "models.yaml", args.model_id)
    output = model_dir / args.output
    if args.output != spec.onnx_file:
        raise RuntimeError("ONNX output filename is not pinned in core/models.yaml")
    if args.verify_only:
        verify_export(output, spec.onnx_size, spec.onnx_sha256)
        print(output)
        return 0
    if spec.distribution == "local-artifact":
        raise RuntimeError(
            "local-artifact ONNX exports must be produced and calibrated by the guarded "
            "training pipeline; use --verify-only for the pinned production graph"
        )
    model = GLiNER.from_pretrained(str(model_dir), local_files_only=True, map_location="cpu")
    exporter = getattr(model, "export_to_onnx", None)
    if not callable(exporter):
        raise RuntimeError(
            "OnnxUnsupported: installed GLiNER revision exposes no maintained export_to_onnx API"
        )
    result = exporter(
        str(model_dir),
        quantized_filename=args.output,
        quantize=True,
    )
    if not output.is_file():
        raise RuntimeError(f"ONNX exporter did not produce {output}: {result}")
    verify_export(output, spec.onnx_size, spec.onnx_sha256)
    print(output)
    return 0


def verify_export(path: Path, expected_size: int, expected_sha256: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"verified ONNX export is absent: {path}")
    if path.stat().st_size != expected_size:
        raise RuntimeError(f"ONNX export size mismatch: {path}")
    with path.open("rb") as model_stream:
        digest = file_digest(model_stream, "sha256").hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(f"ONNX export SHA-256 mismatch: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
