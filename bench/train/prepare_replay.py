#!/usr/bin/env python3
"""Build a deterministic, audited union of legacy and new prepared GLiNER rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import chain
from pathlib import Path
from typing import Any

from hushmark_bench.training import (
    load_prepared,
    prepared_record_fingerprint,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]


def build_replay_union(
    *,
    legacy_path: Path,
    new_path: Path,
    output_path: Path,
    manifest_path: Path,
    legacy_source: str,
    new_source: str,
) -> dict[str, Any]:
    if legacy_source == new_source:
        raise ValueError("legacy and new replay sources must differ")
    legacy = load_prepared(legacy_path)
    new = load_prepared(new_path)
    if {str(row.get("source")) for row in legacy} != {legacy_source}:
        raise ValueError("legacy corpus source does not match the configured replay source")
    if {str(row.get("source")) for row in new} != {new_source}:
        raise ValueError("new corpus source does not match the configured new source")

    legacy_ids = {str(row.get("id")) for row in legacy}
    new_ids = {str(row.get("id")) for row in new}
    if len(legacy_ids) != len(legacy) or len(new_ids) != len(new):
        raise ValueError("replay inputs contain duplicate record ids")
    id_overlap = legacy_ids & new_ids
    if id_overlap:
        raise ValueError(f"legacy/new replay id overlap: {len(id_overlap)}")

    legacy_fingerprints = {prepared_record_fingerprint(row) for row in legacy}
    new_fingerprints = {prepared_record_fingerprint(row) for row in new}
    fingerprint_overlap = legacy_fingerprints & new_fingerprints
    if fingerprint_overlap:
        raise ValueError(f"legacy/new replay content overlap: {len(fingerprint_overlap)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    digest = hashlib.sha256()
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        for record in chain(legacy, new):
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            output.write(encoded)
            digest.update(encoded.encode())
    temporary.replace(output_path)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "hushmark-tr legacy/new replay training union",
        "legacy": {
            "path": str(legacy_path),
            "source": legacy_source,
            "records": len(legacy),
            "sha256": sha256_file(legacy_path),
        },
        "new": {
            "path": str(new_path),
            "source": new_source,
            "records": len(new),
            "sha256": sha256_file(new_path),
        },
        "output": {
            "path": str(output_path),
            "records": len(legacy) + len(new),
            "sha256": digest.hexdigest(),
        },
        "cross_source_id_overlap": 0,
        "cross_source_content_overlap": 0,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--legacy-source", default="synthetic-full")
    parser.add_argument("--new-source", default="hushmark-dataset-prep-v1")
    args = parser.parse_args()
    manifest_path = args.manifest or args.output.with_suffix(".manifest.json")
    manifest = build_replay_union(
        legacy_path=args.legacy.resolve(),
        new_path=args.new.resolve(),
        output_path=args.output.resolve(),
        manifest_path=manifest_path.resolve(),
        legacy_source=args.legacy_source,
        new_source=args.new_source,
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
