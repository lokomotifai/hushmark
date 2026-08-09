import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("INV-02 forwards zero requests when the detection engine is unavailable", async () => {
  const core = new FakeCore();
  core.available = false;
  const upstream = new FakeUpstream();
  const app = buildServer({ config: testConfig(), policy: testPolicy(), core, upstream });
  const response = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: "10000000146" }] },
  });
  expect(response.statusCode).toBe(503);
  expect(response.json()).toEqual({
    error: { code: "HM-5030", message: "detection engine unavailable" },
  });
  expect(upstream.requests).toHaveLength(0);
  await app.close();
});
