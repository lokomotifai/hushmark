import { describe, expect, it } from "vitest";

import { MemoryVault, type VaultEvent } from "../../src/vault/memory.js";

describe("MemoryVault", () => {
  it("reuses a placeholder for the same normalized value and session", async () => {
    const vault = new MemoryVault();
    const first = await vault.intern("s1", "[KISI_1]", {
      type: "PERSON",
      value: "İpek",
      ttlSec: 60,
    });
    const second = await vault.intern("s1", "[KISI_7]", {
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
    await vault.put("s1", "[KISI_1]", { type: "PERSON", value: "canary-one", ttlSec: 1 });
    await vault.put("s1", "[TCKN_1]", { type: "TR_TCKN", value: "canary-two", ttlSec: 1 });
    expect(await vault.resolve("s1", "[KISI_1]")).toBeNull();
    now = 3_000;
    expect(await vault.sweep(new Date(now))).toBe(1);
    expect(JSON.stringify(events)).not.toContain("canary");
  });
});
