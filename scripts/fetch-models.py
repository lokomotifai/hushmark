#!/usr/bin/env python3
"""Fetch pinned model files once and verify their declared size and SHA-256."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "core" / "models.yaml"
MODEL_ROOT = ROOT / "models"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_file(path: Path, spec: dict[str, Any]) -> bool:
    if not path.is_file() or path.stat().st_size != spec["size"]:
        return False
    expected = spec.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"model file has no valid SHA-256 declaration: {path.name}")
    return sha256_file(path) == expected


def download_file(url: str, target: Path, spec: dict[str, Any]) -> None:
    partial = target.with_suffix(target.suffix + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": "hushmark-bootstrap/0.1.1"})
    with urllib.request.urlopen(request, timeout=600) as response, partial.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if not validate_file(partial, spec):
        partial.unlink(missing_ok=True)
        raise ValueError(f"downloaded model file failed verification: {target.name}")
    partial.replace(target)


def main() -> int:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    models = registry.get("models") if isinstance(registry, dict) else None
    if not isinstance(models, list) or not models:
        raise ValueError("core/models.yaml must define a non-empty models list")
    for model in models:
        model_id = model["id"]
        source = model["source"]
        revision = model["revision"]
        target_dir = MODEL_ROOT / model_id
        distribution = model.get("distribution", "remote")
        if distribution not in {"remote", "local-artifact"}:
            raise ValueError(f"invalid model distribution: {model_id}")
        local_artifact = distribution == "local-artifact"
        if local_artifact and not target_dir.is_dir():
            print(f"skipping unpublished local model artifact: {target_dir.relative_to(ROOT)}")
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        for file_spec in model["files"]:
            target = target_dir / file_spec["path"]
            if validate_file(target, file_spec):
                print(f"verified existing model file: {target.relative_to(ROOT)}")
                continue
            if local_artifact:
                raise ValueError(f"local model artifact failed verification: {target}")
            url = (
                f"https://huggingface.co/{source}/resolve/{revision}/"
                f"{file_spec.get('remote_path', file_spec['path'])}?download=true"
            )
            print(f"downloading {url}")
            download_file(url, target, file_spec)
            print(f"verified model file: {target.relative_to(ROOT)}")
    models_by_id = {model["id"]: model for model in models}
    for model in models:
        model_id = model["id"]
        target_dir = MODEL_ROOT / model_id
        if model.get("distribution") == "local-artifact" and not target_dir.is_dir():
            continue
        runtime_config = model.get("runtime_config")
        if runtime_config is not None:
            source_config = target_dir / runtime_config["source"]
            target_config = target_dir / runtime_config["target"]
            config = json.loads(source_config.read_text(encoding="utf-8"))
            tokenizer_model = models_by_id[runtime_config["tokenizer_model"]]
            tokenizer_dir = MODEL_ROOT / tokenizer_model["id"]
            if tokenizer_dir != target_dir:
                for file_spec in tokenizer_model["files"]:
                    source = tokenizer_dir / file_spec["path"]
                    destination = target_dir / file_spec["path"]
                    if not validate_file(source, file_spec):
                        raise ValueError(f"tokenizer dependency failed verification: {source}")
                    shutil.copyfile(source, destination)
            target_config.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"materialized offline model config: {target_config.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"model bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
