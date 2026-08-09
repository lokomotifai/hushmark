import type { TokenCredential } from "@azure/core-auth";
import { expect, it, vi } from "vitest";

import { AzureKeyVaultKms, type AzureCryptographyPort } from "../../src/kms/azureKeyVault.js";
import { GcpKms, type GcpKmsPort } from "../../src/kms/gcpKms.js";
import { VaultTransitKms } from "../../src/kms/vaultTransit.js";

it("implements the Vault Transit encrypt/decrypt HTTP contract", async () => {
  let plaintext = "";
  const fetch = vi.fn<typeof globalThis.fetch>(async (input, init) => {
    const url = input instanceof Request ? input.url : input.toString();
    if (typeof init?.body !== "string") throw new Error("expected JSON request body");
    const body = JSON.parse(init.body) as Record<string, string>;
    expect(new Headers(init.headers).get("x-vault-token")).toBe("token");
    if (url.endsWith("/encrypt/key-a")) {
      plaintext = body.plaintext ?? "";
      return Response.json({ data: { ciphertext: "vault:v1:test" } });
    }
    expect(url).toMatch(/\/decrypt\/key-a$/u);
    expect(body.ciphertext).toBe("vault:v1:test");
    return Response.json({ data: { plaintext } });
  });
  const kms = new VaultTransitKms({
    baseUrl: "http://vault.local",
    token: "token",
    fetch,
  });
  const key = new Uint8Array([1, 2, 3]);
  const wrapped = await kms.wrap("key-a", key);
  await expect(kms.unwrap("key-a", wrapped)).resolves.toEqual(key);
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("adapts the Azure wrapKey contract without exposing key bytes", async () => {
  const wrapped = new Uint8Array([9, 8, 7]);
  const port: AzureCryptographyPort = {
    wrapKey: async () => ({ result: wrapped }),
    unwrapKey: async () => ({ result: new Uint8Array([1, 2, 3]) }),
  };
  const credential: TokenCredential = { getToken: () => Promise.resolve(null) };
  const kms = new AzureKeyVaultKms(credential, () => port);
  await expect(kms.wrap("https://vault/key", new Uint8Array([1, 2, 3]))).resolves.toBe(
    Buffer.from(wrapped).toString("base64"),
  );
  await expect(
    kms.unwrap("https://vault/key", Buffer.from(wrapped).toString("base64")),
  ).resolves.toEqual(new Uint8Array([1, 2, 3]));
});

it("adapts the Google Cloud encrypt/decrypt contract", async () => {
  const port: GcpKmsPort = {
    encrypt: async () => [{ ciphertext: new Uint8Array([7, 7]) }],
    decrypt: async () => [{ plaintext: new Uint8Array([4, 5, 6]) }],
  };
  const kms = new GcpKms(port);
  const wrapped = await kms.wrap(
    "projects/p/locations/l/keyRings/r/cryptoKeys/k",
    new Uint8Array([4, 5, 6]),
  );
  expect(wrapped).toBe(Buffer.from([7, 7]).toString("base64"));
  await expect(
    kms.unwrap("projects/p/locations/l/keyRings/r/cryptoKeys/k", wrapped),
  ).resolves.toEqual(new Uint8Array([4, 5, 6]));
});
