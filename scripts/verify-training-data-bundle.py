#!/usr/bin/env python3
"""Verify an extracted Hushmark replay-data bundle before it is consumed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd().resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest = json.loads((ROOT / "BUNDLE-MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("purpose") != "Hushmark approved replay fine-tuning data":
        raise ValueError("unexpected training data bundle purpose")
    expected: dict[str, str] = {}
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
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
        if relative not in expected:
            raise ValueError(f"bundle contains an unlisted file: {relative}")
        if canary in path.read_bytes():
            raise ValueError(f"private corpus canary found in bundle: {relative}")
        if sha256_file(path) != expected[relative]:
            raise ValueError(f"bundle checksum mismatch: {relative}")
        actual.add(relative)
    if actual != set(expected):
        raise ValueError(f"bundle is missing listed files: {sorted(set(expected) - actual)}")
    print(f"verified {len(actual)} allowlisted training data files in {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
