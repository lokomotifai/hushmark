"""Benchmark inference adapters loaded lazily to keep the baseline isolated."""

from __future__ import annotations

import re


def engine_slug(*parts: str) -> str:
    """Build a filesystem-safe engine name so each model/backend is its own row."""

    joined = "-".join(part for part in parts if part)
    return re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
