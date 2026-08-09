from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import hushmark_core.api as api_module
from fastapi.testclient import TestClient
from hushmark_core.api import app
from hushmark_core.engine import DetectionEngine
from hushmark_core.ner.base import NerSpan


class FixtureNerBackend:
    @property
    def model_id(self) -> str:
        return "fixture-ner"

    @property
    def model_sha256(self) -> str:
        return "a" * 64

    def load(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def predict(self, text: str, threshold: float) -> list[NerSpan]:
        del threshold
        value = "Ayşe Yılmaz"
        start = text.find(value)
        return [] if start < 0 else [NerSpan("PERSON", start, start + len(value), 0.94)]


@contextmanager
def fixture_engine() -> Iterator[DetectionEngine]:
    engine = DetectionEngine(FixtureNerBackend())
    original = api_module.get_engine
    api_module.get_engine = lambda: engine
    try:
        yield engine
    finally:
        api_module.get_engine = original


def test_mask_api_combines_ner_and_deterministic_spans() -> None:
    text = "Müşteri Ayşe Yılmaz TCKN 10000000146 IBAN TR330006100519786457841326"
    with fixture_engine(), TestClient(app) as client:
        response = client.post(
            "/v1/mask",
            json={
                "items": [{"id": "m0", "text": text}],
                "language": "tr",
                "session": "s1",
                "include_values": True,
            },
        )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["masked_text"] == "Müşteri [KISI_1] TCKN [TCKN_1] IBAN [IBAN_1]"
    assert [mapping["type"] for mapping in item["mappings"]] == [
        "PERSON",
        "TR_TCKN",
        "TR_IBAN",
    ]
    assert [mapping["value"] for mapping in item["mappings"]] == [
        "Ayşe Yılmaz",
        "10000000146",
        "TR330006100519786457841326",
    ]


def test_mask_api_omits_values_and_reports_collision() -> None:
    with fixture_engine(), TestClient(app) as client:
        response = client.post(
            "/v1/mask",
            json={"items": [{"id": "m0", "text": "Ayşe Yılmaz"}], "language": "tr"},
        )
        collision = client.post(
            "/v1/mask",
            json={"items": [{"id": "m1", "text": "[KISI_1] Ayşe Yılmaz"}]},
        )
    assert "value" not in response.json()["items"][0]["mappings"][0]
    assert collision.status_code == 422
    assert collision.json()["error"]["code"] == "HM-4102"


def test_configured_backend_masks_demo_sentence() -> None:
    if os.getenv("HUSHMARK_CORE_NER_BACKEND", "disabled") == "disabled" and not os.getenv(
        "HUSHMARK_NER_BACKEND"
    ):
        return
    text = "Müşterimiz Ayşe Yılmaz (TCKN 10000000146, IBAN TR330006100519786457841326)"
    with TestClient(app) as client:
        response = client.post(
            "/v1/mask",
            json={"items": [{"id": "m0", "text": text}], "include_values": True},
        )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "[KISI_1]" in item["masked_text"]
    assert "[TCKN_1]" in item["masked_text"]
    assert "[IBAN_1]" in item["masked_text"]
