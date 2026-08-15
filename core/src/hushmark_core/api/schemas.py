"""Strict pydantic v2 API envelopes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hushmark_core.taxonomy_gen import ENTITY_TYPES

MAX_ITEMS_PER_REQUEST = 128
MAX_ITEM_ID_LENGTH = 128
MAX_TEXT_CODE_POINTS = 65_536
MAX_TOTAL_TEXT_CODE_POINTS = 262_144
MAX_SESSION_LENGTH = 128


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextItem(StrictModel):
    id: str = Field(min_length=1, max_length=MAX_ITEM_ID_LENGTH)
    text: str = Field(max_length=MAX_TEXT_CODE_POINTS)


class AnalyzeRequest(StrictModel):
    items: list[TextItem] = Field(min_length=1, max_length=MAX_ITEMS_PER_REQUEST)
    language: Literal["tr", "en"] = "tr"
    session: str | None = Field(default=None, min_length=1, max_length=MAX_SESSION_LENGTH)

    @model_validator(mode="after")
    def validate_request_budget(self) -> AnalyzeRequest:
        if sum(len(item.text) for item in self.items) > MAX_TOTAL_TEXT_CODE_POINTS:
            raise ValueError("request text budget exceeded")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("item identifiers must be unique")
        return self


class MaskRequest(AnalyzeRequest):
    include_values: bool = False
    collision_mode: Literal["reject", "prefix"] = "reject"


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


class MappingRecord(StrictModel):
    placeholder: str
    type: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    value: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    layer: Literal["deterministic", "ner"]

    @model_validator(mode="after")
    def validate_closed_mapping_type(self) -> MappingRecord:
        if self.type not in ENTITY_TYPES:
            raise ValueError("mapping type is outside the closed taxonomy")
        if self.end <= self.start:
            raise ValueError("mapping end must be greater than start")
        return self


class MaskItem(StrictModel):
    id: str
    masked_text: str
    mappings: list[MappingRecord]


class MaskResponse(StrictModel):
    items: list[MaskItem]
    model_id: str
    taxonomy_version: str


class MetadataResponse(StrictModel):
    version: str
    model_id: str
    model_sha256: str | None
    taxonomy_version: str
    backends: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok", "ready", "loading"]
