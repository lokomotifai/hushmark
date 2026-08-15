import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import type { UpstreamPort, UpstreamResponse } from "../../src/upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("rejects a buffered upstream body above the configured byte limit", async () => {
  const body = JSON.stringify({ choices: [{ message: { content: "x".repeat(128) } }] });
  const upstream: UpstreamPort = {
    forward: () => Promise.resolve(response(body)),
  };
  const app = buildServer({
    config: { ...testConfig(), HUSHMARK_UPSTREAM_MAX_RESPONSE_BYTES: 32 },
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  const result = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: "hello" }] },
  });
  expect(result.statusCode).toBe(502);
  expect(result.json()).toEqual({
    error: { code: "HM-5001", message: "upstream provider error" },
  });
  await app.close();
});

function response(value: string): UpstreamResponse {
  const encoded = new TextEncoder().encode(value);
  return {
    statusCode: 200,
    headers: {},
    body: {
      async *[Symbol.asyncIterator]() {
        yield encoded;
      },
      json: () => Promise.resolve(JSON.parse(value)),
      text: () => Promise.resolve(value),
    },
  };
}
