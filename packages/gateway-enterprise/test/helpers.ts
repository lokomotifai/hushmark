import { generateKeyPairSync } from "node:crypto";

import {
  PolicySchema,
  type CorePort,
  type GatewayConfig,
  type StaticPolicy,
  type UpstreamPort,
  type UpstreamResponse,
} from "@hushmark/gateway";
import type { MaskRequest, MaskResponse } from "@hushmark/shared";

import { hashSecret, MemoryIdentityRepository } from "../src/admin/identity.js";
import type { Clock } from "../src/audit/writer.js";
import { LocalTestKms } from "../src/kms/local.js";
import type { UnsignedLicense } from "../src/license/schema.js";
import { signLicensePayload } from "../src/license/verify.js";
import { buildEnterpriseServer, type EnterpriseRuntime } from "../src/server.js";

export const API_KEY = "hm_k1_1234567890abcdef";
export const API_KEY_ID = "10000000-0000-4000-8000-000000000099";
export const ADMIN_PASSWORD = "correct horse battery staple";
export const SESSION_ID = "019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21";
export const CANARY_NAME = "Ayşe Yılmaz";
export const CANARY_TCKN = "10000000146";
export const CANARY_IBAN = "TR330006100519786457841326";
export const DEMO_TEXT = `Müşterimiz ${CANARY_NAME} TCKN ${CANARY_TCKN} IBAN ${CANARY_IBAN}`;

export class TestClock implements Clock {
  constructor(public instant = new Date("2026-08-09T00:00:00.000Z")) {}

  now(): Date {
    return new Date(this.instant);
  }

  set(value: string): void {
    this.instant = new Date(value);
  }
}

export interface EnterpriseHarness {
  runtime: EnterpriseRuntime;
  identity: MemoryIdentityRepository;
  upstream: RecordingUpstream;
  clock: TestClock;
}

export async function enterpriseHarness(): Promise<EnterpriseHarness> {
  const clock = new TestClock();
  const identity = new MemoryIdentityRepository();
  const passwordHash = await hashSecret(ADMIN_PASSWORD);
  await Promise.all(
    [
      { id: "10000000-0000-4000-8000-000000000001", email: "admin@example.test", role: "admin" },
      {
        id: "10000000-0000-4000-8000-000000000002",
        email: "operator@example.test",
        role: "operator",
      },
      {
        id: "10000000-0000-4000-8000-000000000003",
        email: "auditor@example.test",
        role: "auditor",
      },
    ].map((user) =>
      identity.putUser({
        ...user,
        role: user.role as "admin" | "operator" | "auditor",
        passwordHash,
        enabled: true,
      }),
    ),
  );
  await identity.putApiKey(
    {
      id: API_KEY_ID,
      name: "test-gateway-key",
      prefix: API_KEY.slice(0, 18),
      revokedAt: null,
      createdAt: clock.now().toISOString(),
    },
    await hashSecret(API_KEY),
  );
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const payload: UnsignedLicense = {
    v: 1,
    licensee: "Example Bank A.Ş.",
    tier: "regulated",
    issued_at: "2026-08-01T00:00:00.000Z",
    expires_at: "2026-09-20T00:00:00.000Z",
    grace_days: 10,
    entitlements: {
      features: ["sso", "kms_vault", "audit_chain", "tedbir_report"],
    },
  };
  const signedLicense = signLicensePayload(
    payload,
    privateKey.export({ type: "pkcs8", format: "pem" }).toString(),
  );
  const upstream = new RecordingUpstream();
  const staticPolicy = testPolicy();
  const runtime = await buildEnterpriseServer({
    gateway: {
      config: testConfig(),
      policy: staticPolicy,
      core: new DeterministicFakeCore(),
      upstream,
    },
    staticPolicy,
    signedLicense,
    identity,
    kms: new LocalTestKms(),
    keyId: "test-master-key",
    publicKeyPem: publicKey.export({ type: "spki", format: "pem" }).toString(),
    clock,
    nowMs: () => clock.now().getTime(),
  });
  return { runtime, identity, upstream, clock };
}

export async function login(runtime: EnterpriseRuntime, email: string): Promise<string> {
  const response = await runtime.app.inject({
    method: "POST",
    url: "/admin/auth/login",
    payload: { email, password: ADMIN_PASSWORD },
  });
  if (response.statusCode !== 200) throw new Error(response.body);
  const header = response.headers["set-cookie"];
  if (typeof header !== "string") throw new Error("missing admin cookie");
  return header.split(";", 1)[0] ?? "";
}

export function testConfig(): GatewayConfig {
  return {
    HUSHMARK_GATEWAY_HOST: "127.0.0.1",
    HUSHMARK_GATEWAY_PORT: 8080,
    HUSHMARK_API_KEYS: [API_KEY],
    HUSHMARK_CORE_URL: "http://127.0.0.1:8000",
    HUSHMARK_OPENAI_UPSTREAM: "http://127.0.0.1:9001",
    HUSHMARK_ANTHROPIC_UPSTREAM: "http://127.0.0.1:9002",
    HUSHMARK_POLICY_PATH: "policy.yaml",
    HUSHMARK_VAULT_MAX_ENTRIES: 100,
    HUSHMARK_VAULT_TTL_SEC: 3_600,
    HUSHMARK_UNMASK_LIMIT: 100,
    HUSHMARK_RATE_LIMIT_MAX: 120,
    HUSHMARK_RATE_LIMIT_WINDOW_SEC: 60,
    HUSHMARK_BODY_LIMIT_BYTES: 1_048_576,
    HUSHMARK_TRUST_PROXY: false,
  };
}

export function testPolicy(): StaticPolicy {
  return PolicySchema.parse({
    version: 1,
    defaults: {
      unknown_entity: "block",
      multimodal: "block",
      collision_mode: "reject",
      response_scan: "off",
    },
    rules: [
      { match: { kvkk_class: "special" }, action: "block" },
      { match: { kvkk_class: "secret" }, action: "block" },
      { match: { types: ["TR_TCKN", "TR_IBAN", "PERSON"] }, action: "mask" },
      { match: { types: ["ORG"] }, action: "allow" },
    ],
  });
}

class DeterministicFakeCore implements CorePort {
  mask(input: MaskRequest): Promise<MaskResponse> {
    return Promise.resolve({
      items: input.items.map((item) => {
        const definitions = [
          {
            type: "PERSON" as const,
            value: CANARY_NAME,
            placeholder: "[KISI_1]",
            layer: "ner" as const,
          },
          {
            type: "TR_TCKN" as const,
            value: CANARY_TCKN,
            placeholder: "[TCKN_1]",
            layer: "deterministic" as const,
          },
          {
            type: "TR_IBAN" as const,
            value: CANARY_IBAN,
            placeholder: "[IBAN_1]",
            layer: "deterministic" as const,
          },
        ];
        let maskedText = item.text;
        const mappings = definitions.flatMap((definition) => {
          const start = item.text.indexOf(definition.value);
          if (start < 0) return [];
          maskedText = maskedText.replaceAll(definition.value, definition.placeholder);
          return [
            {
              placeholder: definition.placeholder,
              type: definition.type,
              start,
              end: start + definition.value.length,
              value: definition.value,
              confidence: 1,
              layer: definition.layer,
            },
          ];
        });
        return { id: item.id, masked_text: maskedText, mappings };
      }),
      model_id: "test-core",
      taxonomy_version: "1",
    });
  }
}

export class RecordingUpstream implements UpstreamPort {
  body = "";

  forward(_kind: "openai" | "anthropic", body: Record<string, unknown>): Promise<UpstreamResponse> {
    this.body = JSON.stringify(body);
    const messages = body.messages;
    const last: unknown = Array.isArray(messages) ? messages.at(-1) : undefined;
    const text =
      typeof last === "object" &&
      last !== null &&
      "content" in last &&
      typeof last.content === "string"
        ? last.content
        : "";
    const response = {
      id: "chatcmpl-enterprise",
      object: "chat.completion",
      created: 1_786_300_000,
      model: "test",
      choices: [{ index: 0, message: { role: "assistant", content: text }, finish_reason: "stop" }],
      usage: { prompt_tokens: 8, completion_tokens: 8, total_tokens: 16 },
    };
    return Promise.resolve({
      statusCode: 200,
      headers: { "content-type": "application/json" },
      body: {
        async *[Symbol.asyncIterator]() {
          yield new TextEncoder().encode(JSON.stringify(response));
        },
        json: () => Promise.resolve(structuredClone(response)),
        text: () => Promise.resolve(JSON.stringify(response)),
      },
    });
  }
}
