"""Bare GLiNER baseline: the zero-shot model with no deterministic layer around it."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, cast

from hushmark_bench.adapters import engine_slug

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL_ROOT = REPO_ROOT / "models"
DEFAULT_THRESHOLD = 0.5
DEFAULT_MODEL_ID = "gliner_multi_pii-v1"

LABELS = {
    "person name": "PERSON",
    "full address": "ADDRESS",
    "organization": "ORG",
    "date of birth": "DOB",
    "medical condition": "HEALTH",
    "religious belief": "RELIGION",
    "ethnic origin": "ETHNICITY",
    "political opinion": "POLITICAL",
    "sexual orientation": "SEXUAL_LIFE",
    "criminal record": "CRIMINAL",
    "biometric data": "BIOMETRIC_REF",
    "trade union membership": "UNION",
    "turkish national identity number": "TR_TCKN",
    "turkish tax number": "TR_VKN",
    "turkish iban": "TR_IBAN",
    "foreign iban": "IBAN_OTHER",
    "credit card number": "CREDIT_CARD",
    "phone number": "TR_PHONE",
    "vehicle license plate": "TR_PLATE",
    "social security number": "TR_SGK",
    "email address": "EMAIL",
    "api key": "SECRET_API_KEY",
    "json web token": "SECRET_JWT",
    "private key": "SECRET_PRIVATE_KEY",
}


class GlinerRawAdapter:
    """Runs the same weights hushmark uses, but without the surrounding pipeline."""

    runtime = "torch"
    model_sha256: str | None = None

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or os.environ.get("HUSHMARK_BENCH_GLINER_MODEL", DEFAULT_MODEL_ID)
        self.name = engine_slug("gliner-raw", self.model_id)
        model_root = Path(os.environ.get("HUSHMARK_BENCH_MODEL_ROOT", DEFAULT_MODEL_ROOT))
        model_dir = model_root / self.model_id
        if not model_dir.is_dir():
            raise FileNotFoundError(
                f"model weights are not installed at {model_dir}; run scripts/fetch-models.py"
            )
        gliner_module = importlib.import_module("gliner")
        model = gliner_module.GLiNER.from_pretrained(
            str(model_dir),
            local_files_only=True,
            map_location="cpu",
        )
        self._model = model.eval()
        threshold = os.environ.get("HUSHMARK_BENCH_GLINER_THRESHOLD")
        self._threshold = float(threshold) if threshold else DEFAULT_THRESHOLD

    def predict(self, text: str) -> list[dict[str, object]]:
        predictions = cast(
            list[dict[str, Any]],
            self._model.predict_entities(text, list(LABELS), threshold=self._threshold),
        )
        spans: list[dict[str, object]] = []
        for prediction in predictions:
            entity_type = LABELS.get(str(prediction["label"]))
            if entity_type is None:
                continue
            spans.append(
                {
                    "type": entity_type,
                    "start": int(prediction["start"]),
                    "end": int(prediction["end"]),
                    "confidence": float(prediction["score"]),
                    "layer": "ner",
                }
            )
        return spans
