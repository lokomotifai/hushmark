from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import httpx

from hushmark_sdk.types import (
    AnalyzeResponse,
    Language,
    MaskResponse,
    Provider,
    TextItem,
)

ERROR_CODES = {
    "HM-4001",
    "HM-4010",
    "HM-4030",
    "HM-4102",
    "HM-4201",
    "HM-4203",
    "HM-4290",
    "HM-4301",
    "HM-5001",
    "HM-5030",
    "HM-5040",
}


class HushmarkError(RuntimeError):
    def __init__(self, code: str, message: str, status: int, types: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.types = tuple(types)


class Hushmark:
    def __init__(
        self,
        *,
        core_url: str,
        gateway_url: str,
        api_key: str,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._core_url = _normalize_url(core_url)
        self._gateway_url = _normalize_url(gateway_url)
        if not api_key.startswith("hm_k1_") or len(api_key) <= len("hm_k1_"):
            raise ValueError("api_key must be a non-empty hm_k1_ gateway key")
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def analyze(
        self,
        items: Sequence[TextItem],
        *,
        language: Language = "tr",
        session: str | None = None,
    ) -> AnalyzeResponse:
        payload: dict[str, object] = {"items": list(items), "language": language}
        if session is not None:
            payload["session"] = session
        result = self._request_json("POST", f"{self._core_url}/v1/analyze", json=payload)
        _validate_core_response(result, "entities")
        return cast(AnalyzeResponse, result)

    def mask(
        self,
        items: Sequence[TextItem],
        *,
        language: Language = "tr",
        session: str | None = None,
        include_values: bool = False,
        collision_mode: str = "reject",
    ) -> MaskResponse:
        if collision_mode not in {"reject", "prefix"}:
            raise ValueError("collision_mode must be reject or prefix")
        payload: dict[str, object] = {
            "items": list(items),
            "language": language,
            "include_values": include_values,
            "collision_mode": collision_mode,
        }
        if session is not None:
            payload["session"] = session
        result = self._request_json("POST", f"{self._core_url}/v1/mask", json=payload)
        _validate_core_response(result, "mappings")
        return cast(MaskResponse, result)

    def chat(
        self,
        provider: Provider,
        payload: Mapping[str, object],
        *,
        session: str | None = None,
    ) -> dict[str, Any]:
        route = "/v1/chat/completions" if provider == "openai" else "/v1/messages"
        headers = {"authorization": f"Bearer {self._api_key}"}
        if session is not None:
            headers["x-hushmark-session"] = session
        return self._request_json(
            "POST",
            f"{self._gateway_url}{route}",
            json=dict(payload),
            headers=headers,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Hushmark:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self._client.request(method, url, json=json, headers=headers)
        if response.is_error:
            raise _error_from_response(response)
        try:
            payload = response.json()
        except ValueError as error:
            raise HushmarkError(
                "HM-5001", "service returned invalid JSON", response.status_code
            ) from error
        if not isinstance(payload, dict):
            raise HushmarkError(
                "HM-5001", "service returned an invalid response", response.status_code
            )
        return cast(dict[str, Any], payload)


def _normalize_url(value: str) -> str:
    url = httpx.URL(value)
    if url.scheme not in {"http", "https"} or not url.host:
        raise ValueError("service URLs must be absolute HTTP(S) URLs")
    return str(url).rstrip("/")


def _error_from_response(response: httpx.Response) -> HushmarkError:
    try:
        payload = response.json()
    except ValueError:
        return HushmarkError(
            "HM-5001", "service returned an invalid error response", response.status_code
        )
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return HushmarkError(
            "HM-5001", "service returned an invalid error response", response.status_code
        )
    body = payload["error"]
    code = body.get("code")
    message = body.get("message")
    types = body.get("types", [])
    if (
        not isinstance(code, str)
        or code not in ERROR_CODES
        or not isinstance(message, str)
        or not isinstance(types, list)
        or not all(isinstance(item, str) for item in types)
    ):
        return HushmarkError(
            "HM-5001", "service returned an invalid error response", response.status_code
        )
    return HushmarkError(code, message, response.status_code, types)


def _validate_core_response(payload: Mapping[str, Any], nested_key: str) -> None:
    if (
        not isinstance(payload.get("model_id"), str)
        or not isinstance(payload.get("taxonomy_version"), str)
        or not isinstance(payload.get("items"), list)
    ):
        raise HushmarkError("HM-5001", "core returned an invalid response", 502)
    for item in payload["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise HushmarkError("HM-5001", "core returned an invalid response", 502)
        if not isinstance(item.get(nested_key), list):
            raise HushmarkError("HM-5001", "core returned an invalid response", 502)
