from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from hushmark_sdk import Hushmark

API_KEY = "hm_k1_1234567890abcdef"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_TEXT = (
    "Müşterimiz Ayşe Yılmaz (TCKN 10000000146, IBAN TR330006100519786457841326) ödeme yapamıyor"
)


@pytest.mark.integration
def test_python_sdk_and_batch_example_against_real_local_stack() -> None:
    subprocess.run(
        [str(REPO_ROOT / "node_modules/.bin/pnpm"), "--filter", "@hushmark/gateway", "build"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    core_port = _free_port()
    gateway_port = _free_port()
    environment = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HUSHMARK_CORE_NER_BACKEND": "onnx",
        "HUSHMARK_CORE_LOG_LEVEL": "error",
        "UV_CACHE_DIR": "/tmp/hushmark-uv-cache",
    }
    with _process(
        [
            "uv",
            "run",
            "uvicorn",
            "hushmark_core.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(core_port),
        ],
        environment,
    ) as core:
        _wait_ready(f"http://127.0.0.1:{core_port}/readyz", core)
        example = subprocess.run(
            [
                sys.executable,
                "examples/python-batch/main.py",
                "--core-url",
                f"http://127.0.0.1:{core_port}",
                "--text",
                DEMO_TEXT,
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        example_payload = json.loads(example.stdout)
        assert "[TCKN_1]" in example_payload["items"][0]["masked_text"]
        assert all("value" not in mapping for mapping in example_payload["items"][0]["mappings"])

        with _process(
            [
                "node",
                "sdk-py/tests/support/gateway.mjs",
                str(gateway_port),
                str(core_port),
                API_KEY,
            ],
            environment,
        ) as gateway:
            _wait_ready(f"http://127.0.0.1:{gateway_port}/healthz", gateway)
            with Hushmark(
                core_url=f"http://127.0.0.1:{core_port}",
                gateway_url=f"http://127.0.0.1:{gateway_port}",
                api_key=API_KEY,
            ) as client:
                analyzed = client.analyze([{"id": "demo", "text": DEMO_TEXT}])
                masked = client.mask([{"id": "demo", "text": DEMO_TEXT}])
                response = client.chat(
                    "openai",
                    {
                        "model": "test",
                        "messages": [{"role": "user", "content": DEMO_TEXT}],
                    },
                )

            assert analyzed["items"][0]["entities"]
            assert "[KISI_1]" in masked["items"][0]["masked_text"]
            assert "Ayşe Yılmaz" in response["choices"][0]["message"]["content"]
            gateway.terminate()
            stdout, _ = gateway.communicate(timeout=5)
            assert "[KISI_1]" in stdout
            assert "[TCKN_1]" in stdout
            assert "[IBAN_1]" in stdout
            assert "Ayşe Yılmaz" not in stdout


@pytest.fixture(autouse=True)
def _offline_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_ready(url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(f"process exited before ready: {stdout}\n{stderr}")
        try:
            if httpx.get(url, timeout=0.2).is_success:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"service did not become ready: {url}")


@contextmanager
def _process(command: list[str], environment: dict[str, str]) -> Iterator[subprocess.Popen[str]]:
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
