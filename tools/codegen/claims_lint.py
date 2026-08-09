#!/usr/bin/env python3
"""Reject product claims that overstate reversible masking or compliance outcomes."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORDLIST = ROOT / "docs" / "claims-wordlist.yaml"
SCAN_ROOTS = [
    ROOT / "docs",
    ROOT / "packages" / "sdk-ts",
    ROOT / "sdk-py",
    ROOT / "apps" / "console",
    ROOT / "packages" / "gateway-enterprise" / "src" / "reports",
]
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".ts", ".tsx", ".py"}


def main() -> int:
    config = yaml.safe_load(WORDLIST.read_text(encoding="utf-8"))
    phrases = config.get("forbidden_phrases", [])
    if not isinstance(phrases, list) or not all(isinstance(item, str) for item in phrases):
        raise ValueError("forbidden_phrases must be a string list")

    findings: list[str] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or path == WORDLIST:
                continue
            text = path.read_text(encoding="utf-8").lower()
            for phrase in phrases:
                if phrase.lower() in text:
                    findings.append(f"{path.relative_to(ROOT)}: forbidden claim: {phrase!r}")

    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"Claim-language lint passed across {len(SCAN_ROOTS)} product surfaces.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
