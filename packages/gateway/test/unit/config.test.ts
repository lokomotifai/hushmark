import { describe, expect, it } from "vitest";

import { loadConfig, PolicySchema } from "../../src/config.js";
import { API_KEY } from "../helpers.js";

describe("configuration boundaries", () => {
  it("rejects unknown HUSHMARK environment keys", () => {
    expect(() =>
      loadConfig({
        HUSHMARK_API_KEYS: API_KEY,
        HUSHMARK_OPENAI_UPSTREAM: "http://openai.test",
        HUSHMARK_ANTHROPIC_UPSTREAM: "http://anthropic.test",
        HUSHMARK_TYPO: "unsafe",
      }),
    ).toThrow(/unknown gateway environment/u);
  });

  it("rejects allow as the unknown-entity default", () => {
    expect(() =>
      PolicySchema.parse({
        version: 1,
        defaults: {
          unknown_entity: "allow",
          multimodal: "block",
          collision_mode: "reject",
          response_scan: "off",
        },
        rules: [{ match: { types: ["PERSON"] }, action: "mask" }],
      }),
    ).toThrow();
  });
});
