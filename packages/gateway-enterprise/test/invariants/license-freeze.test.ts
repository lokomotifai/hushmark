import { afterEach, expect, it } from "vitest";

import { API_KEY, DEMO_TEXT, enterpriseHarness, login } from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("INV-08 freezes admin mutations while runtime traffic remains available", async () => {
  const { runtime, clock } = await enterpriseHarness();
  close = () => runtime.app.close();
  const cookie = await login(runtime, "admin@example.test");
  const policy = {
    name: "regulated",
    priority: 100,
    match: { roles: ["admin"] },
    document: {
      version: 1,
      defaults: {
        unknown_entity: "block",
        multimodal: "block",
        collision_mode: "reject",
        response_scan: "off",
      },
      rules: [{ match: { types: ["TR_TCKN"] }, action: "mask" }],
    },
  };
  const before = await runtime.app.inject({
    method: "POST",
    url: "/admin/policies",
    headers: { cookie },
    payload: policy,
  });
  expect(before.statusCode, before.body).toBe(200);

  clock.set("2026-10-01T00:00:00.000Z");
  expect(await runtime.license.status()).toBe("frozen");
  const frozen = await runtime.app.inject({
    method: "POST",
    url: "/admin/policies",
    headers: { cookie },
    payload: policy,
  });
  expect(frozen.statusCode).toBe(403);
  expect(frozen.json()).toMatchObject({ error: { code: "HM-4301" } });

  const traffic = await runtime.app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: DEMO_TEXT }] },
  });
  expect(traffic.statusCode, traffic.body).toBe(200);
});
