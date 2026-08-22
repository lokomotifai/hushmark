#!/usr/bin/env python3
"""Fetch the immutable, safetensors-only BERTurk base snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = "dbmdz/bert-base-turkish-cased"
REVISION = "b6e1de16c983e0f2c70664591ea3f22810072608"
WEIGHTS_SHA256 = "18e29c6c61a046ab18fa48aeec3dce1285b09c5648d9ba68da1474940b9a9fcd"
REQUIRED_FILES = ("config.json", "model.safetensors", "tokenizer_config.json", "vocab.txt")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=REVISION,
        allow_patterns=[*REQUIRED_FILES, "README.md"],
        local_dir=args.output,
    )
    missing = [name for name in REQUIRED_FILES if not (args.output / name).is_file()]
    if missing:
        raise FileNotFoundError(f"BERTurk snapshot is incomplete: {missing}")
    if sha256_file(args.output / "model.safetensors") != WEIGHTS_SHA256:
        raise ValueError("BERTurk base weights do not match the pinned SHA-256")
    manifest = {
        "schema_version": 1,
        "model_id": MODEL_ID,
        "revision": REVISION,
        "license": "MIT",
        "files": {
            path.name: {"size": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(args.output.iterdir())
            if path.is_file() and path.name != "BASE-MODEL-MANIFEST.json"
        },
    }
    (args.output / "BASE-MODEL-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
