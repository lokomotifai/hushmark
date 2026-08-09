import { expect, it } from "vitest";

import { AzureKeyVaultKms } from "../../src/kms/azureKeyVault.js";
import { GcpKms } from "../../src/kms/gcpKms.js";
import { VaultTransitKms } from "../../src/kms/vaultTransit.js";

const provider = process.env.HUSHMARK_NET_KMS_PROVIDER;
const keyId = process.env.HUSHMARK_NET_KMS_KEY_ID ?? "";

it.runIf(provider === "azure")("round-trips a data key through Azure Key Vault", async () => {
  await roundTrip(new AzureKeyVaultKms());
});

it.runIf(provider === "gcp")("round-trips a data key through Google Cloud KMS", async () => {
  await roundTrip(new GcpKms());
});

it.runIf(provider === "vault")("round-trips a data key through Vault Transit", async () => {
  await roundTrip(
    new VaultTransitKms({
      baseUrl: process.env.HUSHMARK_VAULT_ADDR ?? "",
      token: process.env.HUSHMARK_VAULT_TOKEN ?? "",
      mount: process.env.HUSHMARK_VAULT_TRANSIT_MOUNT ?? "transit",
    }),
  );
});

async function roundTrip(kms: {
  wrap(id: string, value: Uint8Array): Promise<string>;
  unwrap(id: string, value: string): Promise<Uint8Array>;
}) {
  const original = new Uint8Array(32).fill(42);
  const wrapped = await kms.wrap(keyId, original);
  expect(wrapped).not.toContain(Buffer.from(original).toString("base64"));
  await expect(kms.unwrap(keyId, wrapped)).resolves.toEqual(original);
}
