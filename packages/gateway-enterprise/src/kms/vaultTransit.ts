import { GatewayError } from "@hushmark/gateway";
import { z } from "zod";

import type { Kms } from "./types.js";

const EncryptResponseSchema = z
  .object({ data: z.object({ ciphertext: z.string().min(1) }).loose() })
  .loose();
const DecryptResponseSchema = z
  .object({ data: z.object({ plaintext: z.string().min(1) }).loose() })
  .loose();

export interface VaultTransitOptions {
  baseUrl: string;
  token: string;
  mount?: string;
  fetch?: typeof globalThis.fetch;
}

export class VaultTransitKms implements Kms {
  readonly #baseUrl: string;
  readonly #mount: string;
  readonly #fetch: typeof globalThis.fetch;

  constructor(private readonly options: VaultTransitOptions) {
    this.#baseUrl = new URL(options.baseUrl).toString().replace(/\/$/u, "");
    this.#mount = options.mount ?? "transit";
    this.#fetch = options.fetch ?? globalThis.fetch;
  }

  async wrap(keyId: string, dataKey: Uint8Array): Promise<string> {
    const response = await this.call(`encrypt/${encodeURIComponent(keyId)}`, {
      plaintext: Buffer.from(dataKey).toString("base64"),
    });
    return EncryptResponseSchema.parse(response).data.ciphertext;
  }

  async unwrap(keyId: string, wrappedKey: string): Promise<Uint8Array> {
    const response = await this.call(`decrypt/${encodeURIComponent(keyId)}`, {
      ciphertext: wrappedKey,
    });
    return new Uint8Array(
      Buffer.from(DecryptResponseSchema.parse(response).data.plaintext, "base64"),
    );
  }

  private async call(operation: string, body: Record<string, string>): Promise<unknown> {
    try {
      const response = await this.#fetch(`${this.#baseUrl}/v1/${this.#mount}/${operation}`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-vault-token": this.options.token,
        },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error("vault transit rejected the request");
      return await response.json();
    } catch {
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }
}
