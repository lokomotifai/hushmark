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
RELEASE_VERSION = "0.1.1"


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
    gateway = (DOCKER_DIR / "gateway.Dockerfile").read_text(encoding="utf-8")
    assert "deploy/docker/eval" not in gateway


def check_compose() -> None:
    compose = yaml.safe_load((DOCKER_DIR / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert {"core", "gateway", "console", "postgres", "vault", "fake-upstream"} <= set(services)
    for name in ("core", "gateway", "console", "fake-upstream", "postgres", "vault"):
        assert services[name]["read_only"] is True
        assert "no-new-privileges:true" in services[name]["security_opt"]
        assert services[name]["cap_drop"] == ["ALL"]
        assert services[name]["networks"] == ["evaluation"]
    assert compose["networks"]["evaluation"]["internal"] is True
    assert services["gateway"]["ports"] == ["127.0.0.1:8080:8080"]
    assert services["console"]["ports"] == ["127.0.0.1:3000:3000"]


def check_production_compose() -> None:
    path = DOCKER_DIR / "compose.production.yaml"
    content = path.read_text(encoding="utf-8")
    compose = yaml.safe_load(content)
    services = compose["services"]
    assert set(services) == {"core", "gateway", "caddy"}
    expected_images = {
        "core": (
            "ghcr.io/hushmark/core@"
            "sha256:98ebc594b2817d3c1c46c5d422886a1374c24bbd25fe53c18bbeb2b026a63c7b"
        ),
        "gateway": (
            "ghcr.io/hushmark/gateway@"
            "sha256:423d01f2b32dea264bef3b9bbe7fa697b28dd776979488dde8e58c79cd534515"
        ),
        "caddy": (
            "caddy:2.10.2-alpine@"
            "sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d"
        ),
    }
    for name, image in expected_images.items():
        service = services[name]
        assert service["image"] == image
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert "build" not in service

    assert "ports" not in services["core"]
    assert "ports" not in services["gateway"]
    assert services["core"]["networks"] == ["backend"]
    assert services["gateway"]["networks"] == ["edge", "backend"]
    assert compose["networks"]["backend"]["internal"] is True
    assert services["core"]["volumes"][0]["read_only"] is True
    assert services["core"]["volumes"][0]["bind"]["create_host_path"] is False

    gateway_environment = services["gateway"]["environment"]
    assert "HUSHMARK_API_KEYS" not in gateway_environment
    assert "HUSHMARK_OPENAI_API_KEY" not in gateway_environment
    assert "HUSHMARK_ANTHROPIC_API_KEY" not in gateway_environment
    assert gateway_environment["HUSHMARK_TRUST_PROXY_HOPS"] == ("${HUSHMARK_TRUST_PROXY_HOPS:-1}")
    assert gateway_environment["HUSHMARK_BODY_LIMIT_BYTES"] == (
        "${HUSHMARK_BODY_LIMIT_BYTES:-1048576}"
    )
    assert services["gateway"]["secrets"] == [
        "hushmark_api_keys",
        "openai_api_key",
        "anthropic_api_key",
        "core_service_token",
    ]
    assert set(compose["secrets"]) == {
        "hushmark_api_keys",
        "openai_api_key",
        "anthropic_api_key",
        "core_service_token",
    }

    assert "fake-upstream" not in content
    assert "hushmark-evaluation" not in content
    assert "POSTGRES_PASSWORD" not in content
    assert "VAULT_DEV_ROOT_TOKEN_ID" not in content
    assert (DOCKER_DIR / "production" / "policy.yaml").read_bytes() == (
        ROOT / "packages/gateway/policy.yaml"
    ).read_bytes()
    entrypoint = (DOCKER_DIR / "production" / "gateway-entrypoint.sh").read_text(encoding="utf-8")
    assert "set -eu" in entrypoint
    assert "set -x" not in entrypoint
    assert "/run/secrets/hushmark_api_keys" in entrypoint
    caddyfile = (DOCKER_DIR / "production" / "Caddyfile").read_text(encoding="utf-8")
    assert "reverse_proxy gateway:8080" in caddyfile
    assert "Strict-Transport-Security" in caddyfile


def check_chart() -> None:
    chart = yaml.safe_load((CHART_DIR / "Chart.yaml").read_text(encoding="utf-8"))
    values = yaml.safe_load((CHART_DIR / "values.yaml").read_text(encoding="utf-8"))
    shared_values = yaml.safe_load((CHART_DIR / "values.shared.yaml").read_text(encoding="utf-8"))
    schema = json.loads((CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))
    assert chart["version"] == chart["appVersion"] == "0.1.1"
    assert values["networkPolicy"]["enabled"] is True
    assert values["networkPolicy"]["externalEgressCidrs"] == []
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
    for migration in (
        "0001_security_hardening.sql",
        "0002_vault_session_keys.sql",
        "0003_vault_placeholder_counters.sql",
    ):
        assert (ROOT / "packages/gateway-enterprise/drizzle" / migration).is_file()
    rendered_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (CHART_DIR / "templates").glob("*.yaml")
    )
    assert "readOnlyRootFilesystem: true" in rendered_sources
    assert "runAsNonRoot: true" in rendered_sources
    assert "policyTypes: [Ingress, Egress]" in rendered_sources
    assert "podSelector: {}" in rendered_sources
    installer = (ROOT / "deploy/airgap/install.sh").read_text(encoding="utf-8")
    assert '--from-literal=core-service-token="$(openssl rand -hex 32)"' in installer


def main() -> None:
    check_versions()
    check_dockerfiles()
    check_compose()
    check_production_compose()
    check_chart()
    print("Container and Helm packaging contracts passed.")


if __name__ == "__main__":
    main()
