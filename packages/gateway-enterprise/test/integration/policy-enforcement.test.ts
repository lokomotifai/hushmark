import { afterEach, expect, it } from "vitest";

import { API_KEY, API_KEY_ID, DEMO_TEXT, enterpriseHarness, testPolicy } from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("enforces the selected enterprise policy for the authenticated API key", async () => {
  const { runtime, upstream } = await enterpriseHarness();
  close = () => runtime.app.close();
  const policy = testPolicy();
  await runtime.policies?.upsert({
    id: "30000000-0000-4000-8000-000000000099",
    name: "block-person-for-key",
    priority: 100,
    match: { api_key_ids: [API_KEY_ID] },
    document: {
      ...policy,
      rules: [{ match: { types: ["PERSON"] }, action: "block" }, ...policy.rules],
    },
  });

  const response = await runtime.app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: DEMO_TEXT }] },
  });

  expect(response.statusCode).toBe(422);
  expect(response.json()).toMatchObject({ error: { code: "HM-4201", types: ["PERSON"] } });
  expect(upstream.body).toBe("");
});
