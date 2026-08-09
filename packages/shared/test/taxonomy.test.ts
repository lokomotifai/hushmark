import { describe, expect, it } from "vitest";

import { ENTITY_TYPES, ERROR_CODES, TAXONOMY, TAXONOMY_VERSION } from "../src/index.js";

describe("generated taxonomy", () => {
  it("exports the closed v1 entity set", () => {
    expect(TAXONOMY_VERSION).toBe(1);
    expect(ENTITY_TYPES).toHaveLength(24);
    expect(TAXONOMY.TR_TCKN.tr_label).toBe("TCKN");
    expect(TAXONOMY.HEALTH.default_action).toBe("block");
  });

  it("exports the closed error-code set", () => {
    expect(ERROR_CODES).toContain("HM-5030");
    expect(new Set(ERROR_CODES).size).toBe(ERROR_CODES.length);
  });
});
