import { describe, expect, it } from "vitest";

import { MemoryVault, type VaultEvent } from "../../src/vault/memory.js";

const SCOPE = { tenantId: "tenant-1", sessionId: "s1" };

describe("MemoryVault", () => {
  it("reuses a placeholder for the same normalized value and session", async () => {
    const vault = new MemoryVault();
    const first = await vault.intern(SCOPE, "[KISI_1]", {
      type: "PERSON",
      value: "İpek",
      ttlSec: 60,
    });
    const second = await vault.intern(SCOPE, "[KISI_7]", {
      type: "PERSON",
      value: "İpek",
      ttlSec: 60,
    });
    expect(second).toBe(first);
  });

  it("expires records and evicts the least-recently-used entry without value logging", async () => {
    let now = 1_000;
    const events: VaultEvent[] = [];
    const vault = new MemoryVault(
      1,
      () => now,
      (event) => events.push(event),
    );
    await vault.put(SCOPE, "[KISI_1]", { type: "PERSON", value: "canary-one", ttlSec: 1 });
    await vault.put(SCOPE, "[TCKN_1]", {
      type: "TR_TCKN",
      value: "canary-two",
      ttlSec: 1,
    });
    expect(await vault.resolve(SCOPE, "[KISI_1]")).toBeNull();
    now = 3_000;
    expect(await vault.sweep(new Date(now))).toBe(1);
    expect(JSON.stringify(events)).not.toContain("canary");
  });

  it("isolates identical session and placeholder values between authenticated tenants", async () => {
    const vault = new MemoryVault();
    const otherScope = { tenantId: "tenant-2", sessionId: SCOPE.sessionId };
    await vault.put(SCOPE, "[KISI_1]", { type: "PERSON", value: "Ayşe", ttlSec: 60 });
    await vault.put(otherScope, "[KISI_1]", { type: "PERSON", value: "Fatih", ttlSec: 60 });
    await expect(vault.resolve(SCOPE, "[KISI_1]")).resolves.toBe("Ayşe");
    await expect(vault.resolve(otherScope, "[KISI_1]")).resolves.toBe("Fatih");
  });
});
