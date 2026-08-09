#!/usr/bin/env python3
"""Generate configuration and API references from runtime fields and route declarations."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from hushmark_core.config import Settings

ROOT = Path(__file__).resolve().parents[1]

GATEWAY_DESCRIPTIONS = {
    "HUSHMARK_GATEWAY_HOST": ("0.0.0.0", "Gateway listen address."),
    "HUSHMARK_GATEWAY_PORT": ("8080", "Gateway listen port."),
    "HUSHMARK_API_KEYS": ("required", "Comma-separated `hm_k1_…` client keys."),
    "HUSHMARK_CORE_URL": ("http://127.0.0.1:8000", "Private core base URL."),
    "HUSHMARK_OPENAI_UPSTREAM": ("required", "OpenAI-compatible upstream base URL."),
    "HUSHMARK_ANTHROPIC_UPSTREAM": ("required", "Anthropic-compatible upstream base URL."),
    "HUSHMARK_OPENAI_API_KEY": ("unset", "Optional upstream OpenAI bearer credential."),
    "HUSHMARK_ANTHROPIC_API_KEY": ("unset", "Optional upstream Anthropic credential."),
    "HUSHMARK_POLICY_PATH": ("packages/gateway/policy.yaml", "Static policy file."),
    "HUSHMARK_VAULT_MAX_ENTRIES": ("100000", "Open vault LRU capacity."),
    "HUSHMARK_VAULT_TTL_SEC": ("86400", "Open vault entry TTL in seconds."),
}

ENTERPRISE_ROWS = {
    "HUSHMARK_ADMIN_EMAIL": ("required", "Local administrator identity."),
    "HUSHMARK_ADMIN_PASSWORD": ("required", "Local administrator bootstrap password."),
    "HUSHMARK_DATABASE_URL": ("required", "PostgreSQL connection URL."),
    "HUSHMARK_KMS_KIND": ("required", "`vault`, `azure`, or `gcp`."),
    "HUSHMARK_KMS_KEY_ID": ("required", "Provider-specific wrapping key identifier."),
    "HUSHMARK_LICENSE_FILE": ("required", "Signed offline license JSON path."),
    "HUSHMARK_LICENSE_PUBLIC_KEY_FILE": ("required", "ed25519 verification key path."),
    "HUSHMARK_VAULT_ADDR": ("provider-specific", "Vault API address when KMS kind is Vault."),
    "HUSHMARK_VAULT_TOKEN": ("secret", "Vault token when KMS kind is Vault."),
    "HUSHMARK_VAULT_TRANSIT_MOUNT": ("transit", "Vault Transit mount name."),
    "HUSHMARK_GATEWAY_URL": ("http://127.0.0.1:8080", "Console server-side gateway URL."),
}

ROUTE_DESCRIPTIONS = {
    ("GET", "/healthz"): "Process liveness; no authentication.",
    ("GET", "/readyz"): "Readiness, including the gateway's transitive core check.",
    ("GET", "/v1/metadata"): "Core version, model, taxonomy, and backend metadata.",
    ("POST", "/v1/analyze"): "Core batch analysis with code-point spans.",
    ("POST", "/v1/mask"): "Core batch analysis plus reversible placeholders.",
    ("POST", "/v1/chat/completions"): "OpenAI-compatible buffered or SSE request.",
    ("POST", "/v1/messages"): "Anthropic-compatible buffered or SSE request.",
    ("POST", "/admin/auth/login"): "Create a local admin session.",
    ("POST", "/admin/auth/logout"): "Destroy the current admin session.",
    ("GET", "/admin/policies"): "List policies.",
    ("POST", "/admin/policies"): "Create or update a policy.",
    ("DELETE", "/admin/policies/:id"): "Delete a policy.",
    ("GET", "/admin/api-keys"): "List redacted API-key metadata.",
    ("POST", "/admin/api-keys"): "Create an API key.",
    ("DELETE", "/admin/api-keys/:id"): "Revoke an API key.",
    ("GET", "/admin/providers"): "List provider configuration metadata.",
    ("POST", "/admin/providers"): "Update provider configuration metadata.",
    ("GET", "/admin/audit/events"): "Page through no-value audit events.",
    ("GET", "/admin/audit/export"): "Export audit NDJSON.",
    ("GET", "/admin/audit/verify"): "Verify the current audit chain.",
    ("POST", "/admin/vault/resolve"): "Role-gated placeholder resolution.",
    ("GET", "/admin/license"): "Inspect license state and entitlements.",
    ("GET", "/admin/metrics/summary"): "Aggregate dashboard counters.",
    ("GET", "/admin/reports/tedbir"): "Generate an entitled Tedbir PDF.",
}


def gateway_keys() -> set[str]:
    source = (ROOT / "packages/gateway/src/config.ts").read_text(encoding="utf-8")
    return set(re.findall(r"^\s{4}(HUSHMARK_[A-Z0-9_]+): z", source, re.MULTILINE))


def declared_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    sources = [
        ROOT / "core/src/hushmark_core/api/__init__.py",
        ROOT / "packages/gateway/src/server.ts",
        ROOT / "packages/gateway-enterprise/src/admin/routes.ts",
    ]
    patterns = [
        re.compile(r'@app\.(get|post|delete|patch)\("([^\"]+)"'),
        re.compile(r'app\.(get|post|delete|patch)\("([^\"]+)"'),
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            routes.update((method.upper(), route) for method, route in pattern.findall(text))
    return routes


def provider_fields(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8").split("export class", maxsplit=1)[0]
    return re.findall(r"^\s{4}([a-z_]+): z\.", source, re.MULTILINE)


def render_config() -> str:
    discovered = gateway_keys()
    if discovered != set(GATEWAY_DESCRIPTIONS):
        drift = sorted(discovered ^ GATEWAY_DESCRIPTIONS.keys())
        raise ValueError(f"gateway config documentation drift: {drift}")
    core_rows = []
    for name, field in Settings.model_fields.items():
        env_name = f"HUSHMARK_CORE_{name.upper()}"
        if field.default_factory is not None:
            default = "dynamic"
        elif isinstance(field.default, Path):
            default = f"<repo>/{field.default.relative_to(ROOT)}"
        else:
            default = str(field.default)
        core_rows.append(
            (env_name, default, field.description or f"Validated core `{name}` setting.")
        )
    lines = [
        "# Configuration reference",
        "",
        "<!-- Generated by scripts/generate-docs.py; edit the generator, not this file. -->",
        "",
        "Unknown gateway `HUSHMARK_` keys are rejected. Core keys use the `HUSHMARK_CORE_` prefix.",
        "Secrets should come from a secret manager or Kubernetes Secret, never a committed file.",
        "",
    ]
    for title, rows in (
        ("Core", sorted(core_rows)),
        ("Gateway", [(key, *GATEWAY_DESCRIPTIONS[key]) for key in sorted(discovered)]),
        (
            "Enterprise and console",
            [(key, *ENTERPRISE_ROWS[key]) for key in sorted(ENTERPRISE_ROWS)],
        ),
    ):
        lines.extend(
            [
                f"## {title}",
                "",
                "| Variable | Default / requirement | Meaning |",
                "| --- | --- | --- |",
                *[
                    f"| `{key}` | `{default}` | {description} |"
                    for key, default, description in rows
                ],
                "",
            ]
        )
    lines.extend(
        [
            "## Policy file",
            "",
            "The strict YAML policy requires `version: 1`, fail-closed defaults, and at least one",
            "rule. Each rule matches closed entity types or a KVKK class. Its action is `allow`,",
            "`mask`, or `block`. Unknown keys and actions are rejected.",
            "",
        ]
    )
    return "\n".join(lines)


def render_api() -> str:
    routes = declared_routes()
    if routes != set(ROUTE_DESCRIPTIONS):
        raise ValueError(f"API documentation drift: {sorted(routes ^ ROUTE_DESCRIPTIONS.keys())}")
    openai_fields = provider_fields(ROOT / "packages/gateway/src/providers/openai.ts")
    anthropic_fields = provider_fields(ROOT / "packages/gateway/src/providers/anthropic.ts")
    lines = [
        "# API reference",
        "",
        "<!-- Generated by scripts/generate-docs.py; edit the generator, not this file. -->",
        "",
        "All request bodies are validated. Provider routes require",
        "`Authorization: Bearer <gateway-key>`.",
        "Admin routes use the local session cookie and RBAC. Error bodies use `error.code` and",
        "`error.message`; malformed input is `HM-4001`.",
        "",
        "## Routes",
        "",
        "| Method | Path | Contract |",
        "| --- | --- | --- |",
        *[
            f"| {method} | `{route}` | {ROUTE_DESCRIPTIONS[(method, route)]} |"
            for method, route in sorted(routes, key=lambda item: (item[1], item[0]))
        ],
        "",
        "## Provider request schemas",
        "",
        f"OpenAI top-level schema fields: {', '.join(f'`{field}`' for field in openai_fields)}.",
        "`model` and `messages` are required; `stream` defaults to false. Text is inspected in",
        "message content/name and supported tool arguments.",
        "",
        "Anthropic top-level schema fields: "
        + ", ".join(f"`{field}`" for field in anthropic_fields)
        + ".",
        "`model`, `max_tokens`, and `messages` are required; `stream` defaults to false. Text is",
        "inspected in system/message content and supported tool input.",
        "",
        "## Core offsets and values",
        "",
        "Core offsets are Unicode code points, end-exclusive. `/v1/mask` omits original values",
        "unless `include_values` is true. Gateway and audit logs do not include request bodies or",
        "mapping values.",
        "",
    ]
    return "\n".join(lines)


def write_or_check(path: Path, content: str, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"generated documentation is stale: {path.relative_to(ROOT)}")
        return
    path.write_text(content, encoding="utf-8")


def format_markdown(content: str) -> str:
    prettier = ROOT / "node_modules/.bin/prettier"
    result = subprocess.run(
        [str(prettier), "--parser", "markdown"],
        input=content,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    write_or_check(ROOT / "docs/config.md", format_markdown(render_config()), args.check)
    write_or_check(ROOT / "docs/api-reference.md", format_markdown(render_api()), args.check)
    print(
        "Generated documentation is current." if args.check else "Generated documentation written."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
