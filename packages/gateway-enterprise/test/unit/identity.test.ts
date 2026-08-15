import { expect, it } from "vitest";

import { issueApiKey, verifySecret } from "../../src/admin/identity.js";

it("keeps a caller-supplied audit identifier separate from the one-time API key secret", async () => {
  const id = "c482d4c5-908b-4d6a-ac4d-6bd9eb2ede6f";
  const issued = await issueApiKey("automation", new Date("2026-08-15T12:00:00.000Z"), id);

  expect(issued.summary).toMatchObject({
    id,
    name: "automation",
    createdAt: "2026-08-15T12:00:00.000Z",
  });
  expect(issued.secret).toMatch(/^hm_k1_[A-Za-z0-9_-]{43}$/u);
  await expect(verifySecret(issued.secretHash, issued.secret)).resolves.toBe(true);
});
