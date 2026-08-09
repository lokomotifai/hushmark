import { expect, it } from "vitest";

import { MemoryAuditStore } from "../../src/audit/store.js";
import { AuditWriter } from "../../src/audit/writer.js";
import { LocalTestKms } from "../../src/kms/local.js";
import { KmsEnvelopeVault } from "../../src/vault/kmsEnvelope.js";
import { MemoryVaultRepository } from "../../src/vault/repository.js";
import { TestClock } from "../helpers.js";

it("round-trips AES-GCM envelope records, preserves stable placeholders, and gates de-mask", async () => {
  const clock = new TestClock();
  const auditStore = new MemoryAuditStore();
  const repository = new MemoryVaultRepository();
  const vault = new KmsEnvelopeVault(
    repository,
    new LocalTestKms(new Uint8Array(32).fill(7)),
    "master",
    new AuditWriter(auditStore, clock),
    () => clock.now().getTime(),
  );
  const first = await vault.intern("session", "[KISI_1]", {
    type: "PERSON",
    value: "Ayşe Yılmaz",
    ttlSec: 60,
  });
  const second = await vault.intern("session", "[KISI_2]", {
    type: "PERSON",
    value: "Ayşe Yılmaz",
    ttlSec: 60,
  });
  expect(first).toBe("[KISI_1]");
  expect(second).toBe(first);
  await expect(vault.resolveAs("auditor", "user:a", "session", first)).rejects.toMatchObject({
    code: "HM-4030",
  });
  await expect(vault.resolveAs("operator", "user:o", "session", first)).resolves.toBe(
    "Ayşe Yılmaz",
  );
  expect(
    Buffer.from((await repository.get("session", first))?.ciphertext ?? []).toString(),
  ).not.toContain("Ayşe Yılmaz");

  clock.set("2026-08-09T00:02:00.000Z");
  expect(await vault.sweep(clock.now())).toBe(1);
  await expect(vault.resolve("session", first)).resolves.toBeNull();
});
