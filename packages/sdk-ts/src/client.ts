import { randomUUID } from "node:crypto";

import type { LanguageModelV4Middleware } from "@ai-sdk/provider";

import { errorFromResponse } from "./errors.js";

export interface HushmarkOptions {
  baseUrl: string;
  apiKey: string;
  sessionId?: string;
  fetch?: typeof globalThis.fetch;
}

export interface HushmarkClient {
  readonly openaiBaseUrl: string;
  readonly anthropicBaseUrl: string;
  readonly sessionId: string;
  readonly fetch: typeof globalThis.fetch;
  middleware(): LanguageModelV4Middleware;
}

export function createHushmark(options: HushmarkOptions): HushmarkClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl);
  if (!options.apiKey.startsWith("hm_k1_") || options.apiKey.length <= "hm_k1_".length) {
    throw new TypeError("apiKey must be a non-empty hm_k1_ gateway key");
  }
  const sessionId = options.sessionId ?? randomUUID();
  assertSessionId(sessionId);
  const baseFetch = options.fetch ?? globalThis.fetch;

  const hushmarkFetch: typeof globalThis.fetch = async (input, init) => {
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    headers.set("authorization", `Bearer ${options.apiKey}`);
    headers.set("x-hushmark-session", sessionId);
    const request = new Request(input, { ...init, headers });
    const response = await baseFetch(request);
    if (!response.ok) throw await errorFromResponse(response);
    return response;
  };

  return {
    openaiBaseUrl: `${baseUrl}/v1`,
    anthropicBaseUrl: baseUrl,
    sessionId,
    fetch: hushmarkFetch,
    middleware: () => ({
      specificationVersion: "v4",
      transformParams: ({ params }) =>
        Promise.resolve({
          ...params,
          headers: {
            ...params.headers,
            authorization: `Bearer ${options.apiKey}`,
            "x-hushmark-session": sessionId,
          },
        }),
      wrapStream: async ({ doStream }) => {
        const result = await doStream();
        return {
          ...result,
          stream: result.stream.pipeThrough(new TransformStream()),
        };
      },
    }),
  };
}

function normalizeBaseUrl(input: string): string {
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
  }
  url.pathname = url.pathname.replace(/\/+$/u, "");
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/u, "");
}

function assertSessionId(value: string): void {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(value)) {
    throw new TypeError("sessionId must be a UUID");
  }
}
