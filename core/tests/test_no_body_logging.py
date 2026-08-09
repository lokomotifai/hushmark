from fastapi.testclient import TestClient
from hushmark_core.api import app


def test_request_body_values_never_enter_logs(capsys: object) -> None:
    from pytest import CaptureFixture

    assert isinstance(capsys, CaptureFixture)
    canary = "10000000146"
    with TestClient(app) as client:
        response = client.post(
            "/v1/analyze",
            json={"items": [{"id": "canary", "text": f"TCKN {canary}"}], "language": "tr"},
        )
    captured = capsys.readouterr()
    assert response.status_code == 200
    assert canary not in captured.err
    assert "request_complete" in captured.err
