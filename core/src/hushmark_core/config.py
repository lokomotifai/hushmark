"""Validated core configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hushmark_core.taxonomy_gen import TAXONOMY


class Settings(BaseSettings):
    """Runtime settings loaded only from the HUSHMARK_CORE_ namespace."""

    model_config = SettingsConfigDict(
        env_prefix="HUSHMARK_CORE_",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    ner_backend: Literal["disabled", "torch", "onnx"] = "torch"
    ner_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    ner_thresholds: dict[str, float] = Field(default_factory=dict)
    model_id: str = "hushmark-tr"
    model_root: Path = Path(__file__).resolve().parents[3] / "models"
    model_registry: Path = Path(__file__).resolve().parents[2] / "models.yaml"
    onnx_model_file: str = "model.onnx"
    service_token: SecretStr | None = None
    service_token_file: Path | None = None
    allow_unauthenticated: bool = False
    body_limit_bytes: int = Field(default=1_048_576, ge=1, le=16_777_216)
    max_concurrency: int = Field(default=4, ge=1, le=128)
    queue_timeout_ms: int = Field(default=250, ge=1, le=30_000)

    @model_validator(mode="after")
    def require_token_when_network_exposed(self) -> Settings:
        if self.service_token is None and self.service_token_file is not None:
            value = self.service_token_file.read_text(encoding="utf-8").strip()
            self.service_token = SecretStr(value)
        if self.service_token is not None and len(self.service_token.get_secret_value()) < 32:
            raise ValueError("HUSHMARK_CORE_SERVICE_TOKEN must contain at least 32 characters")
        if self.service_token is None and not self.allow_unauthenticated:
            raise ValueError(
                "HUSHMARK_CORE_SERVICE_TOKEN is required unless explicit loopback-only "
                "unauthenticated mode is enabled"
            )
        if self.allow_unauthenticated and self.host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("unauthenticated core mode is restricted to loopback")
        return self

    @field_validator("ner_thresholds")
    @classmethod
    def validate_ner_thresholds(cls, value: dict[str, float]) -> dict[str, float]:
        for entity_type, threshold in value.items():
            if entity_type not in TAXONOMY or TAXONOMY[entity_type]["layer"] != "ner":
                raise ValueError(f"NER threshold targets an unknown type: {entity_type}")
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(f"NER threshold is outside [0, 1]: {entity_type}")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-stable validated settings object."""

    legacy_backend = os.getenv("HUSHMARK_NER_BACKEND")
    if legacy_backend and "HUSHMARK_CORE_NER_BACKEND" not in os.environ:
        return Settings.model_validate({"ner_backend": legacy_backend})
    return Settings()
