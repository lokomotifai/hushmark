import fc from "fast-check";
import { expect, it } from "vitest";

import { StreamingUnmasker, unmaskText } from "../../src/streaming/unmasker.js";
import { MemoryVault } from "../../src/vault/memory.js";

it("INV-05 reassembles every arbitrary chunk slicing like whole-text unmasking", async () => {
  await fc.assert(
    fc.asyncProperty(
      fc.array(fc.string({ maxLength: 12 }), { minLength: 1, maxLength: 15 }),
      fc.array(fc.nat({ max: 8 }), { maxLength: 20 }),
      async (parts, sizes) => {
        const vault = new MemoryVault();
        await vault.put("s1", "[KISI_1]", { type: "PERSON", value: "Ayşe İpek", ttlSec: 60 });
        const text = `${parts.join("")}[KISI_1]${[...parts].reverse().join("")}`;
        const expected = await unmaskText(text, "s1", vault);
        const unmasker = new StreamingUnmasker("s1", vault);
        const chunks: string[] = [];
        let cursor = 0;
        for (const size of sizes) {
          if (cursor >= text.length) break;
          const width = Math.max(1, size);
          chunks.push(text.slice(cursor, cursor + width));
          cursor += width;
        }
        chunks.push(text.slice(cursor));
        let actual = "";
        for (const chunk of chunks) actual += await unmasker.push(chunk);
        actual += await unmasker.finish();
        expect(actual).toBe(expected);
      },
    ),
    { numRuns: 200 },
  );
});
