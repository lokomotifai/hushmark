import type { TokenCredential } from "@azure/core-auth";
import { DefaultAzureCredential } from "@azure/identity";
import { CryptographyClient } from "@azure/keyvault-keys";
import { GatewayError } from "@hushmark/gateway";

import type { Kms } from "./types.js";

export interface AzureCryptographyPort {
  wrapKey(algorithm: "RSA-OAEP-256", data: Uint8Array): Promise<{ result: Uint8Array }>;
  unwrapKey(algorithm: "RSA-OAEP-256", data: Uint8Array): Promise<{ result: Uint8Array }>;
}

export class AzureKeyVaultKms implements Kms {
  constructor(
    credential: TokenCredential = new DefaultAzureCredential(),
    private readonly createClient: (keyId: string) => AzureCryptographyPort = (keyId) =>
      new CryptographyClient(keyId, credential),
  ) {}

  async wrap(keyId: string, dataKey: Uint8Array): Promise<string> {
    try {
      const result = await this.createClient(keyId).wrapKey("RSA-OAEP-256", dataKey);
      return Buffer.from(result.result).toString("base64");
    } catch {
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }

  async unwrap(keyId: string, wrappedKey: string): Promise<Uint8Array> {
    try {
      const result = await this.createClient(keyId).unwrapKey(
        "RSA-OAEP-256",
        Buffer.from(wrappedKey, "base64"),
      );
      return new Uint8Array(result.result);
    } catch {
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }
}
