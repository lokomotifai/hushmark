import { generateKeyPairSync } from "node:crypto";

import { expect, it } from "vitest";

import { MemoryAuditStore } from "../../src/audit/store.js";
import { MemoryAuditCheckpointStore } from "../../src/audit/checkpoint.js";
import { AuditWriter } from "../../src/audit/writer.js";
import { LicenseGuard } from "../../src/license/enforce.js";
import type { UnsignedLicense } from "../../src/license/schema.js";
import { signLicensePayload, verifyLicense } from "../../src/license/verify.js";
import { TestClock } from "../helpers.js";

it("verifies ed25519 offline and emits valid, expiring, grace, frozen transitions", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const privatePem = privateKey.export({ type: "pkcs8", format: "pem" }).toString();
  const publicPem = publicKey.export({ type: "spki", format: "pem" }).toString();
  const payload: UnsignedLicense = {
    v: 1,
    licensee: "Example",
    tier: "enterprise",
    issued_at: "2026-01-01T00:00:00.000Z",
    expires_at: "2026-12-31T00:00:00.000Z",
    grace_days: 5,
    entitlements: { features: ["kms_vault", "audit_chain"] },
  };
  const signed = signLicensePayload(payload, privatePem);
  expect(verifyLicense(signed, publicPem)).toEqual(signed);
  expect(verifyLicense({ ...signed, licensee: "Changed" }, publicPem)).toBeNull();

  const clock = new TestClock(new Date("2026-08-09T00:00:00.000Z"));
  const store = new MemoryAuditStore();
  const guard = new LicenseGuard(
    publicPem,
    clock,
    new AuditWriter(store, new Uint8Array(32).fill(9), new MemoryAuditCheckpointStore(), clock),
  );
  expect(await guard.load(signed)).toBe(true);
  expect(await guard.status()).toBe("valid");
  clock.set("2026-12-15T00:00:00.000Z");
  expect(await guard.status()).toBe("expiring");
  clock.set("2027-01-02T00:00:00.000Z");
  expect(await guard.status()).toBe("grace");
  clock.set("2027-01-06T00:00:00.000Z");
  expect(await guard.status()).toBe("frozen");
  await expect(guard.assertMutationAllowed()).rejects.toMatchObject({ code: "HM-4301" });
  expect((await store.list()).filter((event) => event.kind === "LICENSE_CHANGED")).toHaveLength(4);
});
