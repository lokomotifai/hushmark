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
RELEASE_VERSION = "0.1.0"


def check_versions() -> None:
    package_files = [
        ROOT / "package.json",
        ROOT / "apps/console/package.json",
        ROOT / "examples/nextjs-chat/package.json",
        ROOT / "packages/gateway/package.json",
        ROOT / "packages/gateway-enterprise/package.json",
        ROOT / "packages/sdk-ts/package.json",
        ROOT / "packages/shared/package.json",
        ROOT / "tools/license-issuer/package.json",
        ROOT / "tools/release/package.json",
    ]
    for path in package_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("version") == RELEASE_VERSION, f"version drift: {path}"
    python_projects = [
        ROOT / "pyproject.toml",
        ROOT / "bench/pyproject.toml",
        ROOT / "core/pyproject.toml",
        ROOT / "sdk-py/pyproject.toml",
        ROOT / "tools/codegen/pyproject.toml",
    ]
    for path in python_projects:
        content = path.read_text(encoding="utf-8")
        assert f'version = "{RELEASE_VERSION}"' in content, f"version drift: {path}"


def check_dockerfiles() -> None:
    for name in ("core", "gateway", "console"):
        content = (DOCKER_DIR / f"{name}.Dockerfile").read_text(encoding="utf-8")
        assert re.search(r"@sha256:[0-9a-f]{64}", content), f"{name}: base not pinned"
        assert "USER hushmark:hushmark" in content, f"{name}: non-root USER missing"
        assert "HEALTHCHECK" in content, f"{name}: HEALTHCHECK missing"
    core = (DOCKER_DIR / "core.Dockerfile").read_text(encoding="utf-8")
    assert "uv sync --frozen" in core
    assert "FROM runtime AS model" in core and "FROM runtime AS slim" in core
    airgap_core = (DOCKER_DIR / "core-airgap.Dockerfile").read_text(encoding="utf-8")
    assert "model.onnx" in airgap_core
    assert "pytorch_model.bin" not in airgap_core
    assert "model_quantized.onnx" not in airgap_core
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
    shared_values = yaml.safe_load((CHART_DIR / "values.shared.yaml").read_text(encoding="utf-8"))
    schema = json.loads((CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))
    assert chart["version"] == chart["appVersion"] == "0.1.0"
    assert values["networkPolicy"]["enabled"] is True
    assert values["core"]["model"]["baked"] is True
    assert values["postgres"]["enabled"] is False
    assert shared_values["fullnameOverride"] == "hushmark"
    assert shared_values["core"]["model"] == {
        "baked": False,
        "existingClaim": "hushmark-models",
    }
    assert shared_values["console"]["enabled"] is False
    expected_images = {
        "core": (
            "ghcr.io/hushmark/core",
            "sha256:98ebc594b2817d3c1c46c5d422886a1374c24bbd25fe53c18bbeb2b026a63c7b",
        ),
        "gateway": (
            "ghcr.io/hushmark/gateway",
            "sha256:423d01f2b32dea264bef3b9bbe7fa697b28dd776979488dde8e58c79cd534515",
        ),
        "console": (
            "ghcr.io/hushmark/console",
            "sha256:d43296d6193df179bd8930cc4bb513084923cb666b6a5c21cb00985611470b0d",
        ),
    }
    for workload, (repository, digest) in expected_images.items():
        image = shared_values[workload]["image"]
        assert image["repository"] == repository
        assert image["digest"] == digest
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
    check_versions()
    check_dockerfiles()
    check_compose()
    check_chart()
    print("Container and Helm packaging contracts passed.")


if __name__ == "__main__":
    main()
