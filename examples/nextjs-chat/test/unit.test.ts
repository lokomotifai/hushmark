import { expect, it } from "vitest";

import { createHushmark } from "@hushmark/ai-sdk";

it("constructs the three-line adoption surface", () => {
  const hushmark = createHushmark({
    baseUrl: "http://127.0.0.1:8080",
    apiKey: "hm_k1_1234567890abcdef",
  });
  expect(hushmark.openaiBaseUrl).toBe("http://127.0.0.1:8080/v1");
  expect(hushmark.middleware().specificationVersion).toBe("v4");
});
