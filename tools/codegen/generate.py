#!/usr/bin/env python3
"""Generate the Python and TypeScript taxonomy modules from taxonomy.yaml."""

from __future__ import annotations

import argparse
import json
import pprint
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "taxonomy" / "taxonomy.yaml"
TS_TARGET = ROOT / "packages" / "shared" / "src" / "taxonomy.gen.ts"
PY_TARGET = ROOT / "core" / "src" / "hushmark_core" / "taxonomy_gen.py"

REQUIRED_FIELDS = {
    "type",
    "layer",
    "kvkk_class",
    "z_class",
    "default_action",
    "tr_label",
    "description",
}


def load_source() -> tuple[int, list[dict[str, str]]]:
    """Load and validate the single source before rendering either language."""

    raw = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"taxonomy_version", "entities"}:
        raise ValueError("taxonomy root must contain exactly taxonomy_version and entities")
    version = raw["taxonomy_version"]
    entities = raw["entities"]
    if not isinstance(version, int) or version < 1:
        raise ValueError("taxonomy_version must be a positive integer")
    if not isinstance(entities, list) or not entities:
        raise ValueError("entities must be a non-empty list")

    validated: list[dict[str, str]] = []
    seen_types: set[str] = set()
    for index, item in enumerate(entities):
        if not isinstance(item, dict) or set(item) != REQUIRED_FIELDS:
            raise ValueError(f"entity {index} must contain exactly {sorted(REQUIRED_FIELDS)}")
        if not all(isinstance(value, str) and value for value in item.values()):
            raise ValueError(f"entity {index} fields must be non-empty strings")
        entity = dict(item)
        entity_type = entity["type"]
        if entity_type in seen_types:
            raise ValueError(f"duplicate entity type: {entity_type}")
        if not entity_type.isascii() or entity_type.upper() != entity_type:
            raise ValueError(f"entity type is not ASCII UPPER_SNAKE: {entity_type}")
        label = entity["tr_label"]
        if not label.isascii() or not label.isalpha() or label.upper() != label:
            raise ValueError(f"tr_label must be ASCII uppercase letters: {label}")
        if not 2 <= len(label) <= 12:
            raise ValueError(f"tr_label length is outside placeholder grammar: {label}")
        seen_types.add(entity_type)
        validated.append(entity)
    return version, validated


def compact_payload(entities: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Return the cross-language contract fields keyed by stable type."""

    keys = ("layer", "kvkk_class", "z_class", "default_action", "tr_label")
    return {item["type"]: {key: item[key] for key in keys} for item in entities}


def render_typescript(version: int, entities: list[dict[str, str]]) -> str:
    payload = compact_payload(entities)
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    types = json.dumps([item["type"] for item in entities], ensure_ascii=True, indent=2)
    return "\n".join(
        [
            "// GENERATED — do not edit. Source: taxonomy/taxonomy.yaml",
            "",
            f"export const TAXONOMY_VERSION = {version} as const;",
            f"export const ENTITY_TYPES = {types} as const;",
            "export type EntityType = (typeof ENTITY_TYPES)[number];",
            "",
            f"export const TAXONOMY = {pretty} as const;",
            "",
        ]
    )


def render_python(version: int, entities: list[dict[str, str]]) -> str:
    payload = compact_payload(entities)
    pretty = json.dumps(payload, ensure_ascii=False, indent=4)
    entity_types = tuple(item["type"] for item in entities)
    type_tuple = pprint.pformat(entity_types, width=88, sort_dicts=False)
    return "\n".join(
        [
            "# GENERATED — do not edit. Source: taxonomy/taxonomy.yaml",
            "",
            "from __future__ import annotations",
            "",
            "from typing import Final, Literal, TypedDict",
            "",
            "",
            "class TaxonomyEntry(TypedDict):",
            '    layer: Literal["deterministic", "ner"]',
            '    kvkk_class: Literal["general", "special", "secret"]',
            '    z_class: Literal["Z0", "Z1", "Z2", "Z3", "Z4", "Z5"]',
            '    default_action: Literal["mask", "redact", "block", "allow"]',
            "    tr_label: str",
            "",
            "",
            f"TAXONOMY_VERSION: Final = {version}",
            f"ENTITY_TYPES: Final = {type_tuple}",
            f"TAXONOMY: Final[dict[str, TaxonomyEntry]] = {pretty}",
            "",
        ]
    )


def write_or_check(target: Path, content: str, check: bool) -> bool:
    """Write one generated file or report whether its committed form matches."""

    if check:
        return target.exists() and target.read_text(encoding="utf-8") == content
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when generated output drifts")
    args = parser.parse_args()
    version, entities = load_source()
    outputs = {
        TS_TARGET: render_typescript(version, entities),
        PY_TARGET: render_python(version, entities),
    }
    stale = [
        target
        for target, content in outputs.items()
        if not write_or_check(target, content, args.check)
    ]
    if stale:
        for target in stale:
            print(f"stale generated file: {target.relative_to(ROOT)}")
        return 1
    if not args.check:
        print(f"generated {len(outputs)} taxonomy modules for {len(entities)} entity types")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
