"""Validated core configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded only from the HUSHMARK_CORE_ namespace."""

    model_config = SettingsConfigDict(
        env_prefix="HUSHMARK_CORE_",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    ner_backend: Literal["disabled", "torch", "onnx"] = "disabled"
    ner_threshold: float = Field(default=0.55, ge=0.0, le=1.0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-stable validated settings object."""

    return Settings()
