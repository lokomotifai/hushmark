from __future__ import annotations

from typing import Any

import httpx
import pytest
from hushmark_sdk import Hushmark, HushmarkError

API_KEY = "hm_k1_1234567890abcdef"


def test_mask_analyze_and_chat_route_to_the_expected_service() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/analyze":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "m0", "entities": []}],
                    "model_id": "test",
                    "taxonomy_version": "1",
                },
            )
        if request.url.path == "/v1/mask":
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "m0", "masked_text": "hello", "mappings": []}],
                    "model_id": "test",
                    "taxonomy_version": "1",
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hello"}}]},
        )

    with Hushmark(
        core_url="http://core.local/",
        gateway_url="http://gateway.local/",
        api_key=API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.analyze([{"id": "m0", "text": "hello"}])
        client.mask([{"id": "m0", "text": "hello"}])
        client.chat(
            "openai",
            {"model": "test", "messages": [{"role": "user", "content": "hello"}]},
        )

    assert [request.url.host for request in seen] == ["core.local", "core.local", "gateway.local"]
    assert seen[0].headers.get("authorization") is None
    assert seen[2].headers["authorization"] == f"Bearer {API_KEY}"


def test_structured_failures_are_typed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"code": "HM-5030", "message": "detection engine unavailable"}},
        )

    client = Hushmark(
        core_url="http://core.local",
        gateway_url="http://gateway.local",
        api_key=API_KEY,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(HushmarkError) as caught:
        client.analyze([{"id": "m0", "text": "hello"}])
    client.close()

    assert caught.value.code == "HM-5030"
    assert caught.value.status == 503


def test_invalid_core_payload_fails_closed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": "not-a-list"})

    client = Hushmark(
        core_url="http://core.local",
        gateway_url="http://gateway.local",
        api_key=API_KEY,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(HushmarkError, match="invalid response"):
        client.mask([{"id": "m0", "text": "hello"}])
    client.close()


def test_chat_accepts_anthropic_payloads() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["session"] = request.headers.get("x-hushmark-session")
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    with Hushmark(
        core_url="http://core.local",
        gateway_url="http://gateway.local",
        api_key=API_KEY,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.chat(
            "anthropic",
            {"model": "test", "max_tokens": 32, "messages": []},
            session="019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21",
        )

    assert captured == {
        "path": "/v1/messages",
        "session": "019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21",
    }
