import type {
  LanguageModelV4,
  LanguageModelV4CallOptions,
  LanguageModelV4StreamPart,
} from "@ai-sdk/provider";
import { describe, expect, it, vi } from "vitest";

import { createHushmark } from "../src/index.js";

const API_KEY = "hm_k1_1234567890abcdef";
const SESSION_ID = "019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21";

describe("createHushmark", () => {
  it("rejects credential-bearing HTTP outside loopback by default", () => {
    expect(() =>
      createHushmark({
        baseUrl: "http://gateway.example.test",
        apiKey: API_KEY,
      }),
    ).toThrow(/must use HTTPS/u);
  });

  it("derives provider URLs and injects only gateway credentials", async () => {
    const baseFetch = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}"));
    const client = createHushmark({
      baseUrl: "http://localhost:8080/",
      apiKey: API_KEY,
      sessionId: SESSION_ID,
      fetch: baseFetch,
    });

    expect(client.openaiBaseUrl).toBe("http://localhost:8080/v1");
    expect(client.anthropicBaseUrl).toBe("http://localhost:8080");
    await client.fetch("http://localhost:8080/v1/chat/completions", {
      headers: { "x-provider-secret": "must-not-be-used-as-auth" },
    });

    const request = baseFetch.mock.calls[0]?.[0];
    expect(request).toBeInstanceOf(Request);
    if (!(request instanceof Request)) throw new Error("expected Request");
    expect(request.headers.get("authorization")).toBe(`Bearer ${API_KEY}`);
    expect(request.headers.get("x-hushmark-session")).toBe(SESSION_ID);
  });

  it("turns a structured gateway failure into HushmarkError", async () => {
    const client = createHushmark({
      baseUrl: "http://localhost:8080",
      apiKey: API_KEY,
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          Response.json(
            { error: { code: "HM-5030", message: "detection engine unavailable" } },
            { status: 503 },
          ),
        ),
    });

    await expect(client.fetch("http://localhost:8080/healthz")).rejects.toMatchObject({
      name: "HushmarkError",
      code: "HM-5030",
      status: 503,
    });
  });

  it("adds session headers through the AI SDK v7 middleware contract", async () => {
    const middleware = createHushmark({
      baseUrl: "http://localhost:8080",
      apiKey: API_KEY,
      sessionId: SESSION_ID,
    }).middleware();
    const params = { prompt: [], headers: { "x-existing": "yes" } } as LanguageModelV4CallOptions;
    const transformed = await middleware.transformParams?.({
      type: "stream",
      params,
      model: {} as never,
    });

    expect(transformed?.headers).toEqual({
      "x-existing": "yes",
      authorization: `Bearer ${API_KEY}`,
      "x-hushmark-session": SESSION_ID,
    });
    expect(middleware.wrapStream).toBeTypeOf("function");
  });

  it("uses request-scoped sessions by default and stable sessions only when explicitly scoped", async () => {
    const baseFetch = vi.fn<typeof fetch>().mockResolvedValue(new Response("{}"));
    const client = createHushmark({
      baseUrl: "http://localhost:8080",
      apiKey: API_KEY,
      fetch: baseFetch,
    });
    await client.fetch("http://localhost:8080/v1/chat/completions");
    await client.fetch("http://localhost:8080/v1/chat/completions");
    const first = baseFetch.mock.calls[0]?.[0];
    const second = baseFetch.mock.calls[1]?.[0];
    if (!(first instanceof Request) || !(second instanceof Request)) {
      throw new Error("expected Request instances");
    }
    expect(first.headers.get("x-hushmark-session")).not.toBe(
      second.headers.get("x-hushmark-session"),
    );

    const scoped = client.withSession(SESSION_ID);
    expect(scoped.sessionId).toBe(SESSION_ID);
  });

  it("preserves every AI SDK v7 stream part through wrapStream", async () => {
    const middleware = createHushmark({
      baseUrl: "http://localhost:8080",
      apiKey: API_KEY,
    }).middleware();
    if (middleware.wrapStream === undefined) throw new Error("wrapStream is required");
    const parts = [
      { type: "text-start", id: "t0" },
      { type: "text-delta", id: "t0", delta: "merhaba" },
      { type: "text-end", id: "t0" },
    ] as const satisfies readonly LanguageModelV4StreamPart[];
    const wrapped = await middleware.wrapStream({
      doGenerate: () => Promise.reject(new Error("not called")),
      doStream: () =>
        Promise.resolve({
          stream: new ReadableStream<LanguageModelV4StreamPart>({
            start(controller) {
              parts.forEach((part) => controller.enqueue(part));
              controller.close();
            },
          }),
        }),
      params: { prompt: [] },
      model: {} as LanguageModelV4,
    });

    const received: LanguageModelV4StreamPart[] = [];
    const reader = wrapped.stream.getReader();
    for (;;) {
      const part = await reader.read();
      if (part.done) break;
      received.push(part.value);
    }
    expect(received).toEqual(parts);
  });
});
