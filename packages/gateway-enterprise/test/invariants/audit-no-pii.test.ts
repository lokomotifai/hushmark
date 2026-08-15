import { afterEach, expect, it } from "vitest";

import { verifyAuditChain } from "../../src/audit/verify.js";
import {
  API_KEY,
  AUDIT_INTEGRITY_KEY,
  CANARY_NAME,
  CANARY_TCKN,
  DEMO_TEXT,
  enterpriseHarness,
} from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("INV-07 keeps raw values out of the audit chain after enterprise traffic", async () => {
  const { runtime, upstream } = await enterpriseHarness();
  close = () => runtime.app.close();
  const response = await runtime.app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: DEMO_TEXT }] },
  });

  expect(response.statusCode, response.body).toBe(200);
  expect(upstream.body).toContain("[KISI_1]");
  expect(upstream.body).not.toContain(CANARY_NAME);
  expect(response.body).toContain(CANARY_NAME);
  const events = await runtime.auditStore.list();
  expect(verifyAuditChain(events, 1, "latest", AUDIT_INTEGRITY_KEY).ok).toBe(true);
  expect(JSON.stringify(events)).not.toContain(CANARY_NAME);
  expect(JSON.stringify(events)).not.toContain(CANARY_TCKN);
  expect(events.some((event) => event.kind === "MASK_APPLIED")).toBe(true);
  expect(events.some((event) => event.kind === "VAULT_RESOLVE")).toBe(true);
});
