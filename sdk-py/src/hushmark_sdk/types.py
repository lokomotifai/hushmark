from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

Language = Literal["tr", "en"]
Provider = Literal["openai", "anthropic"]


class TextItem(TypedDict):
    id: str
    text: str


class EntitySpan(TypedDict):
    type: str
    start: int
    end: int
    confidence: float
    layer: Literal["deterministic", "ner"]


class MappingRecord(EntitySpan):
    placeholder: str
    value: NotRequired[str]


class AnalyzeItem(TypedDict):
    id: str
    entities: list[EntitySpan]


class AnalyzeResponse(TypedDict):
    items: list[AnalyzeItem]
    model_id: str
    taxonomy_version: str


class MaskItem(TypedDict):
    id: str
    masked_text: str
    mappings: list[MappingRecord]


class MaskResponse(TypedDict):
    items: list[MaskItem]
    model_id: str
    taxonomy_version: str
