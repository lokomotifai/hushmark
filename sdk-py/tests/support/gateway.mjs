import { buildServer, CoreClient, PolicySchema } from "../../../packages/gateway/dist/index.js";

const gatewayPort = Number(process.argv[2]);
const corePort = Number(process.argv[3]);
const apiKey = process.argv[4];
if (!Number.isInteger(gatewayPort) || !Number.isInteger(corePort) || apiKey === undefined) {
  throw new Error("usage: gateway.mjs <gateway-port> <core-port> <api-key>");
}

const policy = PolicySchema.parse({
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
        types: ["TR_TCKN", "TR_IBAN", "IBAN_OTHER", "PERSON", "ADDRESS", "EMAIL"],
      },
      action: "mask",
    },
    { match: { types: ["ORG"] }, action: "allow" },
  ],
});

const upstream = {
  async forward(_kind, body) {
    process.stdout.write(`FORWARDED ${JSON.stringify(body)}\n`);
    const text = requestText(body);
    const value = {
      id: "chatcmpl-python-sdk",
      object: "chat.completion",
      created: 1_786_300_000,
      model: "test",
      choices: [
        {
          index: 0,
          message: { role: "assistant", content: text },
          finish_reason: "stop",
        },
      ],
      usage: { prompt_tokens: 8, completion_tokens: 8, total_tokens: 16 },
    };
    return {
      statusCode: 200,
      headers: { "content-type": "application/json" },
      body: {
        async *[Symbol.asyncIterator]() {
          yield new TextEncoder().encode(JSON.stringify(value));
        },
        async json() {
          return structuredClone(value);
        },
        async text() {
          return JSON.stringify(value);
        },
      },
    };
  },
};

const config = {
  HUSHMARK_GATEWAY_HOST: "127.0.0.1",
  HUSHMARK_GATEWAY_PORT: gatewayPort,
  HUSHMARK_API_KEYS: [apiKey],
  HUSHMARK_CORE_URL: `http://127.0.0.1:${corePort}`,
  HUSHMARK_OPENAI_UPSTREAM: "http://127.0.0.1:9",
  HUSHMARK_ANTHROPIC_UPSTREAM: "http://127.0.0.1:9",
  HUSHMARK_POLICY_PATH: "policy.yaml",
  HUSHMARK_VAULT_MAX_ENTRIES: 100,
  HUSHMARK_VAULT_TTL_SEC: 60,
};

const app = buildServer({
  config,
  policy,
  core: new CoreClient(config.HUSHMARK_CORE_URL),
  upstream,
});
await app.listen({ host: "127.0.0.1", port: gatewayPort });
process.stdout.write("READY\n");

process.once("SIGTERM", async () => {
  await app.close();
  process.exit(0);
});

function requestText(body) {
  const messages = body.messages;
  if (!Array.isArray(messages)) return "";
  const last = messages.at(-1);
  return typeof last?.content === "string" ? last.content : "";
}
