import { MaskRequestSchema, type MaskRequest, type MaskResponse } from "@hushmark/shared";

import { PolicySchema, type GatewayConfig, type StaticPolicy } from "../src/config.js";
import type { CorePort } from "../src/coreClient.js";
import { GatewayError } from "../src/errors.js";

export const API_KEY = "hm_k1_1234567890abcdef";

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
    HUSHMARK_VAULT_TTL_SEC: 60,
    HUSHMARK_UNMASK_LIMIT: 100,
    HUSHMARK_RATE_LIMIT_MAX: 120,
    HUSHMARK_RATE_LIMIT_WINDOW_SEC: 60,
    HUSHMARK_BODY_LIMIT_BYTES: 1_048_576,
    HUSHMARK_UPSTREAM_MAX_RESPONSE_BYTES: 8_388_608,
    HUSHMARK_UPSTREAM_BODY_TIMEOUT_MS: 60_000,
    HUSHMARK_STREAM_MAX_BUFFER_BYTES: 1_048_576,
    HUSHMARK_STREAM_MAX_STATES: 128,
    HUSHMARK_TRUST_PROXY_HOPS: 0,
  };
}

export function testPolicy(overrides: Record<string, unknown> = {}): StaticPolicy {
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
      {
        match: {
          types: [
            "TR_TCKN",
            "TR_VKN",
            "TR_IBAN",
            "IBAN_OTHER",
            "CREDIT_CARD",
            "TR_PHONE",
            "TR_PLATE",
            "TR_SGK",
            "PERSON",
            "ADDRESS",
            "EMAIL",
          ],
        },
        action: "mask",
      },
      { match: { types: ["ORG"] }, action: "allow" },
    ],
    ...overrides,
  });
}

export class FakeCore implements CorePort {
  available = true;
  calls = 0;

  async mask(input: MaskRequest): Promise<MaskResponse> {
    this.calls += 1;
    if (!this.available) throw new GatewayError("HM-5030", "detection engine unavailable");
    const request = MaskRequestSchema.parse(input);
    return {
      items: request.items.map((item) => {
        if (/\[[A-Z]{2,12}_[1-9][0-9]{0,4}\]/u.test(item.text)) {
          if (request.collision_mode === "reject") {
            throw new GatewayError("HM-4102", "placeholder collision in input");
          }
        }
        const definitions = [
          { type: "PERSON" as const, value: "Ayşe Yılmaz", placeholder: "[KISI_1]" },
          { type: "TR_TCKN" as const, value: "10000000146", placeholder: "[TCKN_1]" },
          { type: "ORG" as const, value: "Örnek AŞ", placeholder: "[KURUM_1]" },
          { type: "HEALTH" as const, value: "tip 2 diyabet", placeholder: "[SAGLIK_1]" },
        ];
        let maskedText = item.text;
        const mappings = [];
        for (const definition of definitions) {
          const start = item.text.indexOf(definition.value);
          if (start < 0) continue;
          const suffix = request.collision_mode === "prefix" ? "#abcdabcdabcdabcd" : "";
          const placeholder = definition.placeholder + suffix;
          maskedText = maskedText.split(definition.value).join(placeholder);
          mappings.push({
            placeholder,
            type: definition.type,
            start,
            end: start + definition.value.length,
            value: definition.value,
            confidence: 1,
            layer:
              definition.type === "PERSON" ||
              definition.type === "ORG" ||
              definition.type === "HEALTH"
                ? ("ner" as const)
                : ("deterministic" as const),
          });
        }
        return { id: item.id, masked_text: maskedText, mappings };
      }),
      model_id: "fake-core",
      taxonomy_version: "1",
    };
  }
}
