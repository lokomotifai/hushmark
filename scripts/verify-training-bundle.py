#!/usr/bin/env python3
"""Verify an extracted AC-1 bundle before executing any bundled code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd().resolve()
FORBIDDEN_SEGMENTS = frozenset({"briefs", "hushmark", "research"})
FORBIDDEN_FILES = frozenset({"EXECUTABLE-PLAN-PROMPT.md", "PLAN-BRIEF.md", "PLAN.md"})


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    checksum_path = ROOT / "SHA256SUMS"
    manifest_path = ROOT / "BUNDLE-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("purpose") != "AC-1 isolated GPU training":
        raise ValueError("unexpected bundle purpose")

    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", maxsplit=1)
        expected[relative] = digest
    actual: set[str] = set()
    canary = ("HUSHMARK-CORPUS-" + "CANARY-7f3a9d").encode()
    for path in sorted(ROOT.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"bundle contains a symlink: {path.relative_to(ROOT)}")
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative == "SHA256SUMS":
            continue
        if Path(relative).name in FORBIDDEN_FILES or any(
            part in FORBIDDEN_SEGMENTS for part in Path(relative).parts
        ):
            raise ValueError(f"bundle contains a forbidden private path: {relative}")
        if canary in path.read_bytes():
            raise ValueError(f"bundle contains the private corpus canary: {relative}")
        if relative not in expected:
            raise ValueError(f"bundle contains an unlisted file: {relative}")
        if sha256_file(path) != expected[relative]:
            raise ValueError(f"bundle checksum mismatch: {relative}")
        actual.add(relative)
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        raise ValueError(f"bundle is missing listed files: {missing}")
    print(f"verified {len(actual)} allowlisted files in {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
