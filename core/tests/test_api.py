from fastapi.testclient import TestClient
from hushmark_core.api import app
from hushmark_core.config import get_settings


def test_analyze_route_is_strict_and_returns_exact_spans() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/analyze",
            json={
                "items": [
                    {
                        "id": "a",
                        "text": "TCKN 10000000146 IBAN TR330006100519786457841326",
                    }
                ],
                "language": "tr",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["taxonomy_version"] == "1"
    assert [
        (entity["type"], entity["start"], entity["end"], entity["layer"])
        for entity in body["items"][0]["entities"]
    ] == [
        ("TR_TCKN", 5, 16, "deterministic"),
        ("TR_IBAN", 22, 48, "deterministic"),
    ]


def test_unknown_request_field_returns_closed_error() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/analyze",
            json={"items": [{"id": "a", "text": "safe"}], "unknown": True},
        )
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "HM-4001", "message": "malformed request"}}


def test_health_readiness_and_metadata() -> None:
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ready"}
        metadata = client.get("/v1/metadata").json()
    assert metadata["model_id"] == "deterministic-v1"
    assert metadata["backends"] == ["torch", "onnx"]
    available = {model["id"]: model for model in metadata["available_models"]}
    assert set(available) == {"hushmark-tr", "gliner_multi_pii-v1", "lfm2.5-encoder-350m-pii"}
    assert available["hushmark-tr"]["backends"] == ["torch", "onnx"]
    assert available["lfm2.5-encoder-350m-pii"]["architecture"] == "token-classification"
    assert available["lfm2.5-encoder-350m-pii"]["backends"] == ["torch"]


def test_core_service_token_protects_value_bearing_routes(monkeypatch) -> None:
    token = "core-service-token-with-at-least-32-characters"
    monkeypatch.setenv("HUSHMARK_CORE_SERVICE_TOKEN", token)
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            unauthorized = client.post("/v1/analyze", json={"items": [{"id": "a", "text": "safe"}]})
            authorized = client.post(
                "/v1/analyze",
                headers={"authorization": f"Bearer {token}"},
                json={"items": [{"id": "a", "text": "safe"}]},
            )
        assert unauthorized.status_code == 401
        assert authorized.status_code == 200
    finally:
        get_settings.cache_clear()


def test_core_rejects_request_bodies_over_the_configured_limit(monkeypatch) -> None:
    monkeypatch.setenv("HUSHMARK_CORE_BODY_LIMIT_BYTES", "32")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/analyze",
                content=b'{"items":[{"id":"a","text":"' + (b"x" * 64) + b'"}]}',
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 413
        assert response.json() == {
            "error": {"code": "HM-4001", "message": "request body too large"}
        }
    finally:
        get_settings.cache_clear()


def test_non_ascii_authorization_is_rejected_without_server_error(monkeypatch) -> None:
    token = "core-service-token-with-at-least-32-characters"
    monkeypatch.setenv("HUSHMARK_CORE_SERVICE_TOKEN", token)
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/metadata",
                headers={"authorization": b"Bearer \xe9"},
            )
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()


def test_openapi_schema_is_not_exposed() -> None:
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 404
