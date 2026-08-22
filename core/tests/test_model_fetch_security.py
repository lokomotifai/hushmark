from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def load_fetch_models() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "fetch-models.py"
    spec = importlib.util.spec_from_file_location("hushmark_fetch_models", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load model fetch script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body: bytes, *, declared_length: int | None = None) -> None:
        self.body = body
        self.offset = 0
        self.headers = {} if declared_length is None else {"Content-Length": str(declared_length)}

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return "https://models.example.test/model.bin"

    def read(self, size: int) -> bytes:
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_download_rejects_oversize_body_and_removes_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_fetch_models()
    body = b"trusted" + b"attacker-controlled-tail"
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(body),
    )
    target = tmp_path / "model.bin"
    spec: dict[str, Any] = {
        "size": len(b"trusted"),
        "sha256": hashlib.sha256(b"trusted").hexdigest(),
    }

    with pytest.raises(ValueError, match="exceeded size limit"):
        module.download_file("https://models.example.test/model.bin", target, spec)

    assert not target.exists()
    assert not target.with_suffix(".bin.partial").exists()


def test_download_rejects_plaintext_transport(tmp_path: Path) -> None:
    module = load_fetch_models()
    with pytest.raises(ValueError, match="require HTTPS"):
        module.download_file(
            "http://models.example.test/model.bin",
            tmp_path / "model.bin",
            {"size": 1, "sha256": hashlib.sha256(b"x").hexdigest()},
        )
