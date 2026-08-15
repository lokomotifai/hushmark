import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";

import { afterEach, expect, it } from "vitest";

import { CoreClient } from "../../src/coreClient.js";
import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, testConfig, testPolicy } from "../helpers.js";

const REPO_ROOT = fileURLToPath(new URL("../../../../", import.meta.url));
let child: ChildProcess | undefined;

afterEach(async () => {
  if (child?.exitCode === null) {
    child.kill("SIGTERM");
    await new Promise<void>((resolve) => child?.once("exit", () => resolve()));
  }
  child = undefined;
});

it("round-trips against the real offline ONNX core over HTTP", async () => {
  const port = await freePort();
  child = spawn(
    "uv",
    ["run", "uvicorn", "hushmark_core.api:app", "--host", "127.0.0.1", "--port", String(port)],
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
  await waitUntilReady(`http://127.0.0.1:${String(port)}/readyz`, child);

  const upstream = new FakeUpstream();
  const config = { ...testConfig(), HUSHMARK_CORE_URL: `http://127.0.0.1:${String(port)}` };
  const app = buildServer({
    config,
    policy: testPolicy(),
    core: new CoreClient(config.HUSHMARK_CORE_URL),
    upstream,
  });
  const response = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: {
      model: "test",
      messages: [
        {
          role: "user",
          content:
            "Müşterimiz Ayşe Yılmaz (TCKN 10000000146, IBAN TR330006100519786457841326) ödeme yapamıyor",
        },
      ],
    },
  });
  expect(response.statusCode, response.body).toBe(200);
  const forwarded = JSON.stringify(upstream.requests);
  expect(forwarded).toContain("[KISI_1]");
  expect(forwarded).toContain("[TCKN_1]");
  expect(forwarded).toContain("[IBAN_1]");
  expect(forwarded).not.toContain("Ayşe Yılmaz");
  expect(response.body).toContain("Ayşe Yılmaz");
  expect(response.body).toContain("10000000146");

  const formatted = [..."10000000146"].join("\u00a0");
  const variant = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: formatted }] },
  });
  expect(variant.statusCode, variant.body).toBe(200);
  expect(JSON.stringify(upstream.requests.at(-1))).not.toContain(formatted);
  expect(JSON.stringify(upstream.requests.at(-1))).toContain("[TCKN_1]");
  expect(variant.body).toContain(formatted);

  const split = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: {
      model: "test",
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: "10000" },
            { type: "text", text: "000146" },
          ],
        },
      ],
    },
  });
  expect(split.statusCode, split.body).toBe(200);
  expect(JSON.stringify(upstream.requests.at(-1))).not.toContain("10000000146");
  expect(JSON.stringify(upstream.requests.at(-1))).toContain("[TCKN_1]");
  await app.close();
}, 90_000);

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
