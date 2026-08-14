import { afterEach, expect, it } from "vitest";

import {
  API_KEY,
  API_KEY_ID,
  DEMO_TEXT,
  SESSION_ID,
  enterpriseHarness,
  login,
} from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("allows operator de-mask and denies auditor de-mask", async () => {
  const { runtime } = await enterpriseHarness();
  close = () => runtime.app.close();
  await runtime.app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}`, "x-hushmark-session": SESSION_ID },
    payload: { model: "test", messages: [{ role: "user", content: DEMO_TEXT }] },
  });
  const operator = await login(runtime, "operator@example.test");
  const auditor = await login(runtime, "auditor@example.test");
  const payload = {
    tenant_id: API_KEY_ID,
    session_id: SESSION_ID,
    placeholder: "[KISI_1]",
  };
  const allowed = await runtime.app.inject({
    method: "POST",
    url: "/admin/vault/resolve",
    headers: { cookie: operator },
    payload,
  });
  expect(allowed.statusCode, allowed.body).toBe(200);
  expect(allowed.json()).toEqual({ value: "Ayşe Yılmaz" });
  const denied = await runtime.app.inject({
    method: "POST",
    url: "/admin/vault/resolve",
    headers: { cookie: auditor },
    payload,
  });
  expect(denied.statusCode).toBe(403);
  expect(denied.json()).toMatchObject({ error: { code: "HM-4030" } });
});
