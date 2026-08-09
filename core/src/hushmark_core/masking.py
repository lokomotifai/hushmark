"""Reversible placeholder masking with collision-safe request scope."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from hushmark_core.engine import Entity
from hushmark_core.taxonomy_gen import TAXONOMY

PLACEHOLDER_PATTERN = re.compile(
    r"\[[A-Z]{2,12}_[1-9][0-9]{0,4}\](?:#[0-9a-f]{4})?",
    flags=re.ASCII,
)


class PlaceholderCollision(ValueError):
    code = "HM-4102"


@dataclass(frozen=True, slots=True)
class MappingRecord:
    placeholder: str
    type: str
    start: int
    end: int
    value: str
    confidence: float
    layer: Literal["deterministic", "ner"]


@dataclass(frozen=True, slots=True)
class MaskResult:
    masked_text: str
    mappings: list[MappingRecord]


def collision_suffix(session: str, text: str) -> str:
    material = f"{session}\0{text}".encode()
    return hashlib.sha256(material).hexdigest()[:4]


def mask_text(
    text: str,
    entities: list[Entity],
    *,
    session: str,
    collision_mode: Literal["reject", "prefix"] = "reject",
) -> MaskResult:
    """Replace selected spans without normalizing or changing untouched bytes."""

    collision = PLACEHOLDER_PATTERN.search(text)
    suffix = ""
    if collision is not None:
        if collision_mode == "reject":
            raise PlaceholderCollision("placeholder grammar already exists in input")
        suffix = f"#{collision_suffix(session, text)}"

    counters: dict[str, int] = {}
    value_to_placeholder: dict[tuple[str, str], str] = {}
    mappings: list[MappingRecord] = []
    replacements: list[tuple[int, int, str]] = []
    for entity in sorted(entities, key=lambda item: (item.start, item.end)):
        if entity.type not in TAXONOMY:
            raise ValueError(f"cannot mask unknown entity type: {entity.type}")
        value = text[entity.start : entity.end]
        label = TAXONOMY[entity.type]["tr_label"]
        comparison_value = unicodedata.normalize("NFC", value)
        key = (entity.type, comparison_value)
        placeholder = value_to_placeholder.get(key)
        if placeholder is None:
            counters[label] = counters.get(label, 0) + 1
            placeholder = f"[{label}_{counters[label]}]{suffix}"
            value_to_placeholder[key] = placeholder
        mappings.append(
            MappingRecord(
                placeholder=placeholder,
                type=entity.type,
                start=entity.start,
                end=entity.end,
                value=value,
                confidence=entity.confidence,
                layer=entity.layer,
            )
        )
        replacements.append((entity.start, entity.end, placeholder))

    masked_text = text
    for start, end, placeholder in reversed(replacements):
        masked_text = masked_text[:start] + placeholder + masked_text[end:]
    return MaskResult(masked_text=masked_text, mappings=mappings)


def unmask_text(masked_text: str, mappings: list[MappingRecord]) -> str:
    """Restore only issued placeholders; unknown placeholders remain unchanged."""

    values = {mapping.placeholder: mapping.value for mapping in mappings}
    return PLACEHOLDER_PATTERN.sub(
        lambda match: values.get(match.group(), match.group()),
        masked_text,
    )
