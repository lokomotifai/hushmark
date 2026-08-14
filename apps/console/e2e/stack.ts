import { generateKeyPairSync } from "node:crypto";

import {
  PolicySchema,
  type CorePort,
  type GatewayConfig,
  type UpstreamPort,
  type UpstreamResponse,
} from "@hushmark/gateway";
import {
  buildEnterpriseServer,
  hashSecret,
  LocalTestKms,
  MemoryIdentityRepository,
  signLicensePayload,
  type Clock,
  type EnterpriseRuntime,
  type UnsignedLicense,
} from "@hushmark/gateway-enterprise";
import type { MaskRequest, MaskResponse } from "@hushmark/shared";

export const GATEWAY_URL = "http://127.0.0.1:31881";
export const API_KEY = "hm_k1_consolee2e123456";
export const ADMIN_EMAIL = "admin@example.test";
export const ADMIN_PASSWORD = "correct horse battery staple";
export const DEMO_TEXT = "Müşterimiz Ayşe Yılmaz TCKN 10000000146";

export async function startEnterpriseStack(): Promise<EnterpriseRuntime> {
  const clock: Clock = { now: () => new Date("2026-08-09T12:30:00.000Z") };
  const identity = new MemoryIdentityRepository();
  await identity.putUser({
    id: "10000000-0000-4000-8000-000000000001",
    email: ADMIN_EMAIL,
    passwordHash: await hashSecret(ADMIN_PASSWORD),
    role: "admin",
    enabled: true,
  });
  await identity.putApiKey(
    {
      id: "10000000-0000-4000-8000-000000000099",
      name: "console-e2e",
      prefix: API_KEY.slice(0, 18),
      revokedAt: null,
      createdAt: clock.now().toISOString(),
    },
    await hashSecret(API_KEY),
  );
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const payload: UnsignedLicense = {
    v: 1,
    licensee: "Console E2E",
    tier: "regulated",
    issued_at: "2026-08-01T00:00:00.000Z",
    expires_at: "2027-08-01T00:00:00.000Z",
    grace_days: 30,
    entitlements: { features: ["kms_vault", "audit_chain", "tedbir_report"] },
  };
  const policy = PolicySchema.parse({
    version: 1,
    defaults: {
      unknown_entity: "block",
      multimodal: "block",
      collision_mode: "reject",
      response_scan: "off",
    },
    rules: [
      { match: { types: ["PERSON", "TR_TCKN"] }, action: "mask" },
      { match: { types: ["ORG"] }, action: "allow" },
      { match: { kvkk_class: "special" }, action: "block" },
      { match: { kvkk_class: "secret" }, action: "block" },
    ],
  });
  const runtime = await buildEnterpriseServer({
    gateway: {
      config: config(),
      policy,
      core: new ConsoleCore(),
      upstream: new EchoUpstream(),
    },
    staticPolicy: policy,
    signedLicense: signLicensePayload(
      payload,
      privateKey.export({ type: "pkcs8", format: "pem" }).toString(),
    ),
    identity,
    kms: new LocalTestKms(),
    keyId: "console-test-key",
    publicKeyPem: publicKey.export({ type: "spki", format: "pem" }).toString(),
    clock,
    nowMs: () => clock.now().getTime(),
    adminSecureCookies: false,
  });
  await runtime.app.listen({ host: "127.0.0.1", port: 31_881 });
  return runtime;
}

function config(): GatewayConfig {
  return {
    HUSHMARK_GATEWAY_HOST: "127.0.0.1",
    HUSHMARK_GATEWAY_PORT: 31_881,
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

class ConsoleCore implements CorePort {
  mask(input: MaskRequest): Promise<MaskResponse> {
    return Promise.resolve({
      items: input.items.map((item) => {
        const entities = [
          { type: "PERSON" as const, value: "Ayşe Yılmaz", placeholder: "[KISI_1]" },
          { type: "TR_TCKN" as const, value: "10000000146", placeholder: "[TCKN_1]" },
        ];
        let maskedText = item.text;
        const mappings = entities.flatMap((entity) => {
          const start = item.text.indexOf(entity.value);
          if (start < 0) return [];
          maskedText = maskedText.replaceAll(entity.value, entity.placeholder);
          return [
            {
              ...entity,
              start,
              end: start + entity.value.length,
              confidence: 1,
              layer: entity.type === "PERSON" ? ("ner" as const) : ("deterministic" as const),
            },
          ];
        });
        return { id: item.id, masked_text: maskedText, mappings };
      }),
      model_id: "console-e2e-core",
      taxonomy_version: "1",
    });
  }
}

class EchoUpstream implements UpstreamPort {
  forward(_kind: "openai" | "anthropic", body: Record<string, unknown>): Promise<UpstreamResponse> {
    const messages = body.messages;
    const last: unknown = Array.isArray(messages) ? messages.at(-1) : undefined;
    const content =
      typeof last === "object" &&
      last !== null &&
      "content" in last &&
      typeof last.content === "string"
        ? last.content
        : "";
    const response = {
      id: "chatcmpl-console-e2e",
      object: "chat.completion",
      created: 1_786_300_000,
      model: "test",
      choices: [{ index: 0, message: { role: "assistant", content }, finish_reason: "stop" }],
    };
    return Promise.resolve({
      statusCode: 200,
      headers: { "content-type": "application/json" },
      body: {
        async *[Symbol.asyncIterator]() {
          await Promise.resolve();
          yield new TextEncoder().encode(JSON.stringify(response));
        },
        json: () => Promise.resolve(structuredClone(response)),
        text: () => Promise.resolve(JSON.stringify(response)),
      },
    });
  }
}
