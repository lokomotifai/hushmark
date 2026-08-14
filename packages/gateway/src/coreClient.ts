import { MaskResponseSchema, type MaskRequest, type MaskResponse } from "@hushmark/shared";
import { Pool } from "undici";

import { GatewayError } from "./errors.js";

export interface CorePort {
  mask(request: MaskRequest): Promise<MaskResponse>;
  ready?(): Promise<boolean>;
  close?(): Promise<void>;
}

export class CoreClient implements CorePort {
  readonly #pool: Pool;
  readonly #path: string;

  constructor(
    baseUrl: string,
    private readonly timeoutMs = 2_000,
    private readonly serviceToken?: string,
  ) {
    const url = new URL("/v1/mask", baseUrl);
    this.#pool = new Pool(url.origin, { connections: 10, pipelining: 1 });
    this.#path = url.pathname;
  }

  async mask(request: MaskRequest): Promise<MaskResponse> {
    try {
      const response = await this.#pool.request({
        path: this.#path,
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(this.serviceToken === undefined
            ? {}
            : { authorization: `Bearer ${this.serviceToken}` }),
        },
        body: JSON.stringify(request),
        headersTimeout: this.timeoutMs,
        bodyTimeout: this.timeoutMs,
      });
      const raw: unknown = await response.body.json();
      if (response.statusCode === 422 && isCollision(raw)) {
        throw new GatewayError("HM-4102", "placeholder collision in input");
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw new GatewayError("HM-5030", "detection engine unavailable");
      }
      const parsed = MaskResponseSchema.safeParse(raw);
      if (!parsed.success) {
        throw new GatewayError("HM-5030", "invalid detection engine response");
      }
      return parsed.data;
    } catch (error) {
      if (error instanceof GatewayError) throw error;
      throw new GatewayError("HM-5030", "detection engine unavailable");
    }
  }

  async ready(): Promise<boolean> {
    try {
      const response = await this.#pool.request({
        path: "/readyz",
        method: "GET",
        headersTimeout: this.timeoutMs,
        bodyTimeout: this.timeoutMs,
      });
      await response.body.dump();
      return response.statusCode === 200;
    } catch {
      return false;
    }
  }

  async close(): Promise<void> {
    await this.#pool.close();
  }
}

function isCollision(value: unknown): boolean {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = value.error;
  return typeof error === "object" && error !== null && "code" in error && error.code === "HM-4102";
}
