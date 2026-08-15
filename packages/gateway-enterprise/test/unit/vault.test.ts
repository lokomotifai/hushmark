import { expect, it } from "vitest";

import { MemoryAuditStore } from "../../src/audit/store.js";
import { MemoryAuditCheckpointStore } from "../../src/audit/checkpoint.js";
import { AuditWriter } from "../../src/audit/writer.js";
import { LocalTestKms } from "../../src/kms/local.js";
import { KmsEnvelopeVault } from "../../src/vault/kmsEnvelope.js";
import { MemoryVaultRepository } from "../../src/vault/repository.js";
import type { EncryptedVaultRecord, VaultRepository } from "../../src/vault/repository.js";
import type { VaultScope } from "@hushmark/gateway";
import type { EntityType } from "@hushmark/shared";
import { TestClock } from "../helpers.js";

const SCOPE = { tenantId: "tenant", sessionId: "session" };

it("round-trips AES-GCM envelope records, preserves stable placeholders, and gates de-mask", async () => {
  const clock = new TestClock();
  const auditStore = new MemoryAuditStore();
  const repository = new MemoryVaultRepository();
  const vault = new KmsEnvelopeVault(
    repository,
    new LocalTestKms(new Uint8Array(32).fill(7)),
    "master",
    new AuditWriter(
      auditStore,
      new Uint8Array(32).fill(9),
      new MemoryAuditCheckpointStore(),
      clock,
    ),
    () => clock.now().getTime(),
  );
  const first = await vault.intern(SCOPE, "[KISI_1]", {
    type: "PERSON",
    value: "Ayşe Yılmaz",
    ttlSec: 60,
  });
  const second = await vault.intern(SCOPE, "[KISI_2]", {
    type: "PERSON",
    value: "Ayşe Yılmaz",
    ttlSec: 60,
  });
  expect(first).toBe("[KISI_1]");
  expect(second).toBe(first);
  await expect(vault.resolveAs("auditor", "user:a", SCOPE, first)).rejects.toMatchObject({
    code: "HM-4030",
  });
  await expect(vault.resolveAs("operator", "user:o", SCOPE, first)).resolves.toBe("Ayşe Yılmaz");
  expect(
    Buffer.from((await repository.get(SCOPE, first))?.ciphertext ?? []).toString(),
  ).not.toContain("Ayşe Yılmaz");

  clock.set("2026-08-09T00:02:00.000Z");
  expect(await vault.sweep(clock.now())).toBe(1);
  await expect(vault.resolve(SCOPE, first)).resolves.toBeNull();
});

it("keeps in-flight key leases valid while an expired cache entry is evicted", async () => {
  let now = 0;
  const repository = new DelayedVaultRepository();
  const vault = new KmsEnvelopeVault(
    repository,
    new LocalTestKms(new Uint8Array(32).fill(7)),
    "master",
    new AuditWriter(
      new MemoryAuditStore(),
      new Uint8Array(32).fill(9),
      new MemoryAuditCheckpointStore(),
    ),
    () => now,
    10_000,
    10,
  );

  const firstWrite = vault.intern(SCOPE, "[KISI_1]", {
    type: "PERSON",
    value: "first-secret",
    ttlSec: 60,
  });
  await repository.firstLookupBlocked;
  now = 11;
  const secondPlaceholder = await vault.intern(SCOPE, "[KISI_2]", {
    type: "PERSON",
    value: "second-secret",
    ttlSec: 60,
  });
  repository.releaseFirstLookup();
  const firstPlaceholder = await firstWrite;

  await expect(vault.resolve(SCOPE, firstPlaceholder)).resolves.toBe("first-secret");
  await expect(vault.resolve(SCOPE, secondPlaceholder)).resolves.toBe("second-secret");
});

class DelayedVaultRepository implements VaultRepository {
  private readonly inner = new MemoryVaultRepository();
  private hmacLookups = 0;
  private markFirstLookupBlocked!: () => void;
  private continueFirstLookup!: () => void;
  readonly firstLookupBlocked = new Promise<void>((resolve) => {
    this.markFirstLookupBlocked = resolve;
  });
  private readonly firstLookupRelease = new Promise<void>((resolve) => {
    this.continueFirstLookup = resolve;
  });

  releaseFirstLookup(): void {
    this.continueFirstLookup();
  }

  claimSessionKey(scope: VaultScope, candidateWrappedKey: string): Promise<string> {
    return this.inner.claimSessionKey(scope, candidateWrappedKey);
  }

  getSessionKey(scope: VaultScope): Promise<string | null> {
    return this.inner.getSessionKey(scope);
  }

  allocatePlaceholder(
    scope: VaultScope,
    label: string,
    suffix: string,
    minimum: number,
  ): Promise<string> {
    return this.inner.allocatePlaceholder(scope, label, suffix, minimum);
  }

  put(record: EncryptedVaultRecord): Promise<void> {
    return this.inner.put(record);
  }

  get(scope: VaultScope, placeholder: string): Promise<EncryptedVaultRecord | null> {
    return this.inner.get(scope, placeholder);
  }

  async getByValueHmac(
    scope: VaultScope,
    entityType: EntityType,
    valueHmac: string,
  ): Promise<EncryptedVaultRecord | null> {
    this.hmacLookups += 1;
    if (this.hmacLookups === 1) {
      this.markFirstLookupBlocked();
      await this.firstLookupRelease;
      return null;
    }
    return this.inner.getByValueHmac(scope, entityType, valueHmac);
  }

  listSession(scope: VaultScope): Promise<EncryptedVaultRecord[]> {
    return this.inner.listSession(scope);
  }

  deleteExpired(at: Date): Promise<number> {
    return this.inner.deleteExpired(at);
  }
}
