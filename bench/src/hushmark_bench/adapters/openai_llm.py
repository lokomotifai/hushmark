"""LLM-as-redactor baseline against the OpenAI API.

Offsets are never requested from the model: LLMs report character positions
unreliably. The model returns surface strings plus an occurrence index, and this
adapter resolves them against the source text. Responses are cached on disk so a
re-run is free and the exact model output stays auditable.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx

from hushmark_bench.adapters import engine_slug

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"

ENTITY_TYPES = (
    "PERSON",
    "ADDRESS",
    "ORG",
    "DOB",
    "HEALTH",
    "RELIGION",
    "ETHNICITY",
    "POLITICAL",
    "SEXUAL_LIFE",
    "CRIMINAL",
    "BIOMETRIC_REF",
    "UNION",
    "TR_TCKN",
    "TR_VKN",
    "TR_IBAN",
    "IBAN_OTHER",
    "CREDIT_CARD",
    "TR_PHONE",
    "TR_PLATE",
    "TR_SGK",
    "EMAIL",
    "SECRET_API_KEY",
    "SECRET_JWT",
    "SECRET_PRIVATE_KEY",
)

SYSTEM_PROMPT = (
    "You extract personal data from Turkish text for a KVKK masking pipeline. "
    "Return every span that belongs to one of the given types. "
    "Copy each span exactly as it appears in the text, without trimming or normalising. "
    "occurrence is 1 for the first appearance of that exact string, 2 for the second. "
    "Recall matters more than precision: emit a span whenever it is plausibly personal data.\n"
    "Types: " + ", ".join(ENTITY_TYPES)
)

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "text", "occurrence"],
                "properties": {
                    "type": {"type": "string", "enum": list(ENTITY_TYPES)},
                    "text": {"type": "string"},
                    "occurrence": {"type": "integer", "minimum": 1},
                },
            },
        }
    },
}


def resolve_offsets(text: str, entities: list[dict[str, Any]]) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    for entity in entities:
        surface = str(entity.get("text", ""))
        if not surface:
            continue
        occurrence = max(1, int(entity.get("occurrence", 1)))
        start = -1
        cursor = 0
        for _ in range(occurrence):
            start = text.find(surface, cursor)
            if start < 0:
                break
            cursor = start + 1
        if start < 0:
            continue
        spans.append(
            {
                "type": str(entity["type"]),
                "start": start,
                "end": start + len(surface),
                "confidence": 1.0,
                "layer": "llm",
            }
        )
    return spans


class OpenAiLlmAdapter:
    runtime = "api"
    model_sha256: str | None = None

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for the openai-llm engine; "
                "this engine calls a third-party API and sends benchmark text off-host"
            )
        self.model_id = os.environ.get("HUSHMARK_BENCH_OPENAI_MODEL", DEFAULT_MODEL)
        # Each model is its own comparison row, so the engine name carries the model id.
        self.name = engine_slug("openai", self.model_id)
        self._endpoint = os.environ.get("HUSHMARK_BENCH_OPENAI_ENDPOINT", DEFAULT_ENDPOINT)
        cache_root = os.environ.get("HUSHMARK_BENCH_OPENAI_CACHE", str(REPO_ROOT / ".cache/openai"))
        self._cache_dir = Path(cache_root) / self.model_id
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            timeout=120.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _cache_path(self, text: str) -> Path:
        digest = hashlib.sha256(
            "\n".join((self.model_id, SYSTEM_PROMPT, text)).encode("utf-8")
        ).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def _complete(self, text: str) -> dict[str, Any]:
        cache_path = self._cache_path(text)
        if cache_path.is_file():
            return dict(json.loads(cache_path.read_text(encoding="utf-8")))
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "pii_entities",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
        }
        response = self._client.post(self._endpoint, json=payload)
        response.raise_for_status()
        body = dict(response.json())
        cache_path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return body

    def predict(self, text: str) -> list[dict[str, object]]:
        body = self._complete(text)
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return []
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            return []
        parsed = json.loads(content)
        entities = parsed.get("entities")
        if not isinstance(entities, list):
            return []
        return resolve_offsets(text, [entity for entity in entities if isinstance(entity, dict)])
