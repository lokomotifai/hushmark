import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";

import { createOpenAI } from "@ai-sdk/openai";
import { createHushmark } from "@hushmark/ai-sdk";
import {
  buildServer,
  CoreClient,
  PolicySchema,
  type GatewayConfig,
  type UpstreamPort,
  type UpstreamResponse,
} from "@hushmark/gateway";
import { generateText, wrapLanguageModel } from "ai";
import { afterEach, expect, it } from "vitest";

const REPO_ROOT = fileURLToPath(new URL("../../../", import.meta.url));
const API_KEY = "hm_k1_1234567890abcdef";
let coreProcess: ChildProcess | undefined;
let closeGateway: (() => Promise<void>) | undefined;

afterEach(async () => {
  await closeGateway?.();
  closeGateway = undefined;
  if (coreProcess?.exitCode === null) {
    coreProcess.kill("SIGTERM");
    await new Promise<void>((resolve) => coreProcess?.once("exit", () => resolve()));
  }
  coreProcess = undefined;
});

it("round-trips through AI SDK v7 middleware, the gateway, and the real core", async () => {
  const corePort = await freePort();
  coreProcess = spawn(
    "uv",
    ["run", "uvicorn", "hushmark_core.api:app", "--host", "127.0.0.1", "--port", String(corePort)],
    {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        HF_HUB_OFFLINE: "1",
        TRANSFORMERS_OFFLINE: "1",
        HUSHMARK_CORE_NER_BACKEND: "onnx",
        HUSHMARK_CORE_LOG_LEVEL: "error",
        UV_CACHE_DIR: "/tmp/hushmark-uv-cache",
      },
      stdio: "ignore",
    },
  );
  await waitUntilReady(`http://127.0.0.1:${String(corePort)}/readyz`, coreProcess);

  const upstream = new RecordingUpstream();
  const gatewayPort = await freePort();
  const config = gatewayConfig(corePort, gatewayPort);
  const app = buildServer({
    config,
    policy: policy(),
    core: new CoreClient(config.HUSHMARK_CORE_URL),
    upstream,
  });
  await app.listen({ host: "127.0.0.1", port: gatewayPort });
  closeGateway = async () => app.close();

  const hushmark = createHushmark({
    baseUrl: `http://127.0.0.1:${String(gatewayPort)}`,
    apiKey: API_KEY,
  });
  const provider = createOpenAI({
    baseURL: hushmark.openaiBaseUrl,
    apiKey: API_KEY,
    fetch: hushmark.fetch,
  });
  const model = wrapLanguageModel({
    model: provider.chat("test"),
    middleware: hushmark.middleware(),
  });
  const prompt =
    "Müşterimiz Ayşe Yılmaz (TCKN 10000000146, IBAN TR330006100519786457841326) ödeme yapamıyor";
  const result = await generateText({ model, prompt });

  expect(upstream.body).toContain("[KISI_1]");
  expect(upstream.body).toContain("[TCKN_1]");
  expect(upstream.body).toContain("[IBAN_1]");
  expect(upstream.body).not.toContain("Ayşe Yılmaz");
  expect(result.text).toContain("Ayşe Yılmaz");
  expect(result.text).toContain("10000000146");
}, 30_000);

class RecordingUpstream implements UpstreamPort {
  body = "";

  async forward(_kind: "openai" | "anthropic", body: Record<string, unknown>) {
    this.body = JSON.stringify(body);
    const text = requestText(body);
    return jsonResponse({
      id: "chatcmpl-sdk",
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
    });
  }
}

function requestText(body: Record<string, unknown>): string {
  const messages = body.messages;
  if (!Array.isArray(messages)) return "";
  const last: unknown = messages.at(-1);
  if (typeof last !== "object" || last === null || !("content" in last)) return "";
  return typeof last.content === "string" ? last.content : "";
}

function jsonResponse(value: Record<string, unknown>): UpstreamResponse {
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
}

function gatewayConfig(corePort: number, gatewayPort: number): GatewayConfig {
  return {
    HUSHMARK_GATEWAY_HOST: "127.0.0.1",
    HUSHMARK_GATEWAY_PORT: gatewayPort,
    HUSHMARK_API_KEYS: [API_KEY],
    HUSHMARK_CORE_URL: `http://127.0.0.1:${String(corePort)}`,
    HUSHMARK_OPENAI_UPSTREAM: "http://127.0.0.1:9",
    HUSHMARK_ANTHROPIC_UPSTREAM: "http://127.0.0.1:9",
    HUSHMARK_POLICY_PATH: "policy.yaml",
    HUSHMARK_VAULT_MAX_ENTRIES: 100,
    HUSHMARK_VAULT_TTL_SEC: 60,
    HUSHMARK_UNMASK_LIMIT: 100,
    HUSHMARK_RATE_LIMIT_MAX: 120,
    HUSHMARK_RATE_LIMIT_WINDOW_SEC: 60,
    HUSHMARK_BODY_LIMIT_BYTES: 1_048_576,
    HUSHMARK_TRUST_PROXY: false,
  };
}

function policy() {
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
          types: ["TR_TCKN", "TR_IBAN", "IBAN_OTHER", "PERSON", "ADDRESS", "EMAIL"],
        },
        action: "mask",
      },
      { match: { types: ["ORG"] }, action: "allow" },
    ],
  });
}

async function freePort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (typeof address !== "object" || address === null) throw new Error("failed to reserve a port");
  await new Promise<void>((resolve, reject) =>
    server.close((error) => (error === undefined ? resolve() : reject(error))),
  );
  return address.port;
}

async function waitUntilReady(url: string, processHandle: ChildProcess): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (processHandle.exitCode !== null) throw new Error("core process exited before ready");
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The socket is expected to refuse connections during model loading.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("core did not become ready");
}
