import { randomUUID } from "node:crypto";

import type { LanguageModelV4Middleware } from "@ai-sdk/provider";

import { errorFromResponse } from "./errors.js";

export interface HushmarkOptions {
  baseUrl: string;
  apiKey: string;
  sessionId?: string;
  fetch?: typeof globalThis.fetch;
  allowInsecureHttp?: boolean;
}

export interface HushmarkClient {
  readonly openaiBaseUrl: string;
  readonly anthropicBaseUrl: string;
  readonly sessionId: string | undefined;
  readonly fetch: typeof globalThis.fetch;
  withSession(sessionId?: string): HushmarkClient;
  middleware(): LanguageModelV4Middleware;
}

export function createHushmark(options: HushmarkOptions): HushmarkClient {
  const baseUrl = normalizeBaseUrl(options.baseUrl, options.allowInsecureHttp ?? false);
  if (!options.apiKey.startsWith("hm_k1_") || options.apiKey.length <= "hm_k1_".length) {
    throw new TypeError("apiKey must be a non-empty hm_k1_ gateway key");
  }
  const sessionId = options.sessionId;
  if (sessionId !== undefined) assertSessionId(sessionId);
  const baseFetch = options.fetch ?? globalThis.fetch;

  const hushmarkFetch: typeof globalThis.fetch = async (input, init) => {
    const requestSessionId = sessionId ?? randomUUID();
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
    headers.set("authorization", `Bearer ${options.apiKey}`);
    headers.set("x-hushmark-session", requestSessionId);
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
    withSession: (scopedSessionId = randomUUID()) =>
      createHushmark({ ...options, sessionId: scopedSessionId, fetch: baseFetch }),
    middleware: () => ({
      specificationVersion: "v4",
      transformParams: ({ params }) => {
        const requestSessionId = sessionId ?? randomUUID();
        return Promise.resolve({
          ...params,
          headers: {
            ...params.headers,
            authorization: `Bearer ${options.apiKey}`,
            "x-hushmark-session": requestSessionId,
          },
        });
      },
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

function normalizeBaseUrl(input: string, allowInsecureHttp: boolean): string {
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
  }
  if (url.protocol === "http:" && !allowInsecureHttp && !isLoopback(url.hostname)) {
    throw new TypeError(
      "non-loopback baseUrl must use HTTPS; allowInsecureHttp is for isolated development only",
    );
  }
  url.pathname = url.pathname.replace(/\/+$/u, "");
  url.search = "";
  url.hash = "";
  return url.toString().replace(/\/$/u, "");
}

function isLoopback(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^\[|\]$/gu, "");
  return normalized === "localhost" || normalized === "::1" || normalized.startsWith("127.");
}

function assertSessionId(value: string): void {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(value)) {
    throw new TypeError("sessionId must be a UUID");
  }
}
