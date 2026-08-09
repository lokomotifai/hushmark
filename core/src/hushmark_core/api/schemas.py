"""Strict pydantic v2 API envelopes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hushmark_core.taxonomy_gen import ENTITY_TYPES


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextItem(StrictModel):
    id: str = Field(min_length=1)
    text: str


class AnalyzeRequest(StrictModel):
    items: list[TextItem] = Field(min_length=1)
    language: Literal["tr", "en"] = "tr"
    session: str | None = None


class EntitySpan(StrictModel):
    type: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    layer: Literal["deterministic", "ner"]

    @model_validator(mode="after")
    def validate_closed_type_and_span(self) -> EntitySpan:
        if self.type not in ENTITY_TYPES:
            raise ValueError("entity type is outside the closed taxonomy")
        if self.end <= self.start:
            raise ValueError("entity end must be greater than start")
        return self


class AnalyzeItem(StrictModel):
    id: str
    entities: list[EntitySpan]


class AnalyzeResponse(StrictModel):
    items: list[AnalyzeItem]
    model_id: str
    taxonomy_version: str


class MetadataResponse(StrictModel):
    version: str
    model_id: str
    model_sha256: str | None
    taxonomy_version: str
    backends: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok", "ready"]
