#!/usr/bin/env python3
"""Fetch pinned model files once and verify their declared size and SHA-256."""

from __future__ import annotations

import hashlib
import json
import shutil
import signal
import sys
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "core" / "models.yaml"
MODEL_ROOT = ROOT / "models"
DOWNLOAD_DEADLINE_SECONDS = 600
SOCKET_TIMEOUT_SECONDS = 30


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


def embed_offline_encoder_config(
    config: dict[str, Any], tokenizer_dir: Path, target_dir: Path
) -> dict[str, Any]:
    """Embed encoder architecture and write a complete local tokenizer config."""

    if config.get("encoder_config") is None:
        encoder_config_path = tokenizer_dir / "config.json"
        encoder_config = json.loads(encoder_config_path.read_text(encoding="utf-8"))
        if not isinstance(encoder_config.get("model_type"), str):
            raise ValueError(f"encoder config is invalid: {encoder_config_path}")
        config["encoder_config"] = encoder_config
        if isinstance(encoder_config.get("vocab_size"), int):
            config["vocab_size"] = encoder_config["vocab_size"]
    runtime_encoder_config = config.get("encoder_config")
    if not isinstance(runtime_encoder_config, dict):
        raise ValueError(f"runtime encoder config is invalid: {target_dir.name}")
    local_encoder_config = dict(runtime_encoder_config)
    # Transformers 5 treats a local tokenizer with an unversioned config as
    # potentially Mistral and applies an unrelated regex warning/fix.
    local_encoder_config.setdefault("transformers_version", "5.0.0")
    (target_dir / "config.json").write_text(
        json.dumps(local_encoder_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config


def download_file(url: str, target: Path, spec: dict[str, Any]) -> None:
    expected_size = spec.get("size")
    if not isinstance(expected_size, int) or expected_size <= 0:
        raise ValueError(f"model file has no valid size declaration: {target.name}")
    if urlparse(url).scheme != "https":
        raise ValueError("model downloads require HTTPS")
    partial = target.with_suffix(target.suffix + ".partial")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "hushmark-bootstrap/0.1.1"})
    completed = False
    downloaded = 0
    try:
        with (
            absolute_deadline(DOWNLOAD_DEADLINE_SECONDS),
            urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT_SECONDS) as response,
            partial.open("xb") as output,
        ):
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("model download redirected to a non-HTTPS URL")
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and int(declared_length) != expected_size:
                raise ValueError(f"model download size declaration mismatch: {target.name}")
            while chunk := response.read(1024 * 1024):
                downloaded += len(chunk)
                if downloaded > expected_size:
                    raise ValueError(f"model download exceeded size limit: {target.name}")
                output.write(chunk)
        if downloaded != expected_size or not validate_file(partial, spec):
            raise ValueError(f"downloaded model file failed verification: {target.name}")
        partial.replace(target)
        completed = True
    finally:
        if not completed:
            partial.unlink(missing_ok=True)


@contextmanager
def absolute_deadline(seconds: int) -> Iterator[None]:
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        yield
        return

    def deadline_exceeded(_signum: int, _frame: object) -> None:
        raise TimeoutError("model download exceeded absolute deadline")

    previous_handler = signal.signal(signal.SIGALRM, deadline_exceeded)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


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
        if distribution not in {"remote", "local-artifact", "private-huggingface"}:
            raise ValueError(f"invalid model distribution: {model_id}")
        if distribution == "private-huggingface":
            print(f"skipping private model; run scripts/install-private-model.py: {model_id}")
            continue
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
        if model.get("distribution") == "private-huggingface":
            continue
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
            embed_offline_encoder_config(config, tokenizer_dir, target_dir)
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
