from fastapi.testclient import TestClient
from hushmark_core.api import app


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
