import type { FastifyInstance } from "fastify";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

describe("provider round-trip", () => {
  let app: FastifyInstance;
  let core: FakeCore;
  let upstream: FakeUpstream;

  beforeEach(async () => {
    core = new FakeCore();
    upstream = new FakeUpstream();
    app = buildServer({ config: testConfig(), policy: testPolicy(), core, upstream });
    await app.ready();
  });

  afterEach(async () => app.close());

  it("serves liveness and core-backed readiness without an API key", async () => {
    const health = await app.inject({ method: "GET", url: "/healthz" });
    const readiness = await app.inject({ method: "GET", url: "/readyz" });

    expect(health.statusCode).toBe(200);
    expect(health.json()).toEqual({ status: "ok" });
    expect(readiness.statusCode).toBe(200);
    expect(readiness.json()).toEqual({ status: "ready" });
  });

  it.each([
    ["openai", false],
    ["openai", true],
    ["anthropic", false],
    ["anthropic", true],
  ] as const)(
    "restores %s output with stream=%s while upstream sees placeholders",
    async (kind, stream) => {
      const path = kind === "openai" ? "/v1/chat/completions" : "/v1/messages";
      const body =
        kind === "openai"
          ? {
              model: "test",
              stream,
              messages: [{ role: "user", content: "Ayşe Yılmaz TCKN 10000000146" }],
            }
          : {
              model: "test",
              max_tokens: 32,
              stream,
              messages: [
                { role: "user", content: [{ type: "text", text: "Ayşe Yılmaz TCKN 10000000146" }] },
              ],
            };
      const response = await app.inject({
        method: "POST",
        url: path,
        headers: { authorization: `Bearer ${API_KEY}` },
        payload: body,
      });
      expect(response.statusCode).toBe(200);
      expect(JSON.stringify(upstream.requests)).not.toContain("Ayşe Yılmaz");
      expect(JSON.stringify(upstream.requests)).not.toContain("10000000146");
      expect(JSON.stringify(upstream.requests)).toContain("[KISI_1]");
      expect(response.body).toContain("Ayşe Yılmaz");
      expect(response.body).toContain("10000000146");
      if (stream && kind === "openai") expect(response.body).toContain("[DONE]");
      if (stream && kind === "anthropic") expect(response.body).toContain("message_stop");
    },
  );

  it("applies buffered response scanning only to non-streaming content fields", async () => {
    await app.close();
    upstream = new FakeUpstream();
    upstream.responseOverride = "Yeni kişi Ayşe Yılmaz";
    const policy = testPolicy({
      defaults: {
        unknown_entity: "block",
        multimodal: "block",
        collision_mode: "reject",
        response_scan: "buffered",
      },
    });
    app = buildServer({ config: testConfig(), policy, core: new FakeCore(), upstream });
    const response = await app.inject({
      method: "POST",
      url: "/v1/chat/completions",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { model: "test", messages: [{ role: "user", content: "Merhaba" }] },
    });
    expect(response.statusCode).toBe(200);
    expect(response.body).toContain("[KISI_1]");
    expect(response.body).not.toContain("Ayşe Yılmaz");
  });
});
