#!/usr/bin/env python3
"""Static release checks for container and Helm packaging."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKER_DIR = ROOT / "deploy" / "docker"
CHART_DIR = ROOT / "deploy" / "helm" / "hushmark"


def check_dockerfiles() -> None:
    for name in ("core", "gateway", "console"):
        content = (DOCKER_DIR / f"{name}.Dockerfile").read_text(encoding="utf-8")
        assert re.search(r"@sha256:[0-9a-f]{64}", content), f"{name}: base not pinned"
        assert "USER hushmark:hushmark" in content, f"{name}: non-root USER missing"
        assert "HEALTHCHECK" in content, f"{name}: HEALTHCHECK missing"
    core = (DOCKER_DIR / "core.Dockerfile").read_text(encoding="utf-8")
    assert "uv sync --frozen" in core
    assert "FROM runtime AS model" in core and "FROM runtime AS slim" in core
    console = (DOCKER_DIR / "console.Dockerfile").read_text(encoding="utf-8")
    assert ".next/standalone" in console


def check_compose() -> None:
    compose = yaml.safe_load((DOCKER_DIR / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"core", "gateway", "console", "postgres", "vault", "fake-upstream"} <= set(services)
    for name in ("core", "gateway", "console", "fake-upstream"):
        assert services[name]["read_only"] is True
        assert "no-new-privileges:true" in services[name]["security_opt"]
    assert services["gateway"]["ports"] == ["127.0.0.1:8080:8080"]
    assert services["console"]["ports"] == ["127.0.0.1:3000:3000"]


def check_chart() -> None:
    chart = yaml.safe_load((CHART_DIR / "Chart.yaml").read_text(encoding="utf-8"))
    values = yaml.safe_load((CHART_DIR / "values.yaml").read_text(encoding="utf-8"))
    schema = json.loads((CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))
    assert chart["version"] == chart["appVersion"] == "0.1.0"
    assert values["networkPolicy"]["enabled"] is True
    assert values["core"]["model"]["baked"] is True
    assert values["postgres"]["enabled"] is False
    assert "postgres" in schema["properties"]
    source = (ROOT / "packages/gateway-enterprise/drizzle/0000_initial.sql").read_bytes()
    packaged = (CHART_DIR / "files/0000_initial.sql").read_bytes()
    assert source == packaged, "Helm PostgreSQL migration drifted from gateway-enterprise"
    rendered_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (CHART_DIR / "templates").glob("*.yaml")
    )
    assert "readOnlyRootFilesystem: true" in rendered_sources
    assert "runAsNonRoot: true" in rendered_sources


def main() -> None:
    check_dockerfiles()
    check_compose()
    check_chart()
    print("Container and Helm packaging contracts passed.")


if __name__ == "__main__":
    main()
