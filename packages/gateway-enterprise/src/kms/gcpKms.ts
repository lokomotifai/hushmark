import { KeyManagementServiceClient } from "@google-cloud/kms";
import { GatewayError } from "@hushmark/gateway";

import type { Kms } from "./types.js";

export interface GcpKmsPort {
  encrypt(input: {
    name: string;
    plaintext: Uint8Array;
  }): Promise<readonly [{ ciphertext?: Uint8Array | string | null }, ...unknown[]]>;
  decrypt(input: {
    name: string;
    ciphertext: Uint8Array;
  }): Promise<readonly [{ plaintext?: Uint8Array | string | null }, ...unknown[]]>;
}

export class GcpKms implements Kms {
  constructor(private readonly client: GcpKmsPort = new KeyManagementServiceClient()) {}

  async wrap(keyId: string, dataKey: Uint8Array): Promise<string> {
    try {
      const [response] = await this.client.encrypt({
        name: keyId,
        plaintext: Buffer.from(dataKey),
      });
      if (response.ciphertext === null || response.ciphertext === undefined) {
        throw new Error("GCP KMS omitted ciphertext");
      }
      return Buffer.from(response.ciphertext).toString("base64");
    } catch {
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }

  async unwrap(keyId: string, wrappedKey: string): Promise<Uint8Array> {
    try {
      const [response] = await this.client.decrypt({
        name: keyId,
        ciphertext: Buffer.from(wrappedKey, "base64"),
      });
      if (response.plaintext === null || response.plaintext === undefined) {
        throw new Error("GCP KMS omitted plaintext");
      }
      return new Uint8Array(
        typeof response.plaintext === "string"
          ? Buffer.from(response.plaintext, "base64")
          : Buffer.from(response.plaintext),
      );
    } catch {
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }
}
