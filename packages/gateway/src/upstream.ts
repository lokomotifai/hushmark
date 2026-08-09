import { request } from "undici";

import type { GatewayConfig } from "./config.js";
import { GatewayError } from "./errors.js";

export interface UpstreamResponse {
  statusCode: number;
  headers: Record<string, string | string[]>;
  body: AsyncIterable<Uint8Array> & { json(): Promise<unknown>; text(): Promise<string> };
}

export interface UpstreamPort {
  forward(
    kind: "openai" | "anthropic",
    body: Record<string, unknown>,
    headers: Record<string, string | string[] | undefined>,
    signal?: AbortSignal,
  ): Promise<UpstreamResponse>;
}

export class HttpUpstream implements UpstreamPort {
  constructor(private readonly config: GatewayConfig) {}

  async forward(
    kind: "openai" | "anthropic",
    body: Record<string, unknown>,
    incomingHeaders: Record<string, string | string[] | undefined>,
    signal?: AbortSignal,
  ): Promise<UpstreamResponse> {
    const base =
      kind === "openai"
        ? this.config.HUSHMARK_OPENAI_UPSTREAM
        : this.config.HUSHMARK_ANTHROPIC_UPSTREAM;
    const path = kind === "openai" ? "/v1/chat/completions" : "/v1/messages";
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (kind === "openai" && this.config.HUSHMARK_OPENAI_API_KEY !== undefined) {
      headers.authorization = `Bearer ${this.config.HUSHMARK_OPENAI_API_KEY}`;
    }
    if (kind === "anthropic") {
      if (this.config.HUSHMARK_ANTHROPIC_API_KEY !== undefined) {
        headers["x-api-key"] = this.config.HUSHMARK_ANTHROPIC_API_KEY;
      }
      const version = incomingHeaders["anthropic-version"];
      if (typeof version === "string") headers["anthropic-version"] = version;
    }
    try {
      const response = await request(new URL(path, base), {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal,
        headersTimeout: 30_000,
        bodyTimeout: 0,
      });
      if (response.statusCode < 200 || response.statusCode >= 300) {
        await response.body.dump();
        throw new GatewayError("HM-5001", "upstream provider error");
      }
      return response as UpstreamResponse;
    } catch (error) {
      if (error instanceof GatewayError) throw error;
      throw new GatewayError("HM-5001", "upstream provider error");
    }
  }
}
