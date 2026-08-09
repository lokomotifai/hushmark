import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("INV-03 never forwards a masked canary", async () => {
  const upstream = new FakeUpstream();
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: {
      model: "test",
      messages: [{ role: "user", content: "Ayşe Yılmaz 10000000146" }],
    },
  });
  const forwarded = JSON.stringify(upstream.requests);
  expect(forwarded).not.toContain("Ayşe Yılmaz");
  expect(forwarded).not.toContain("10000000146");

  const blocked = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: "tanı tip 2 diyabet" }] },
  });
  expect(blocked.statusCode).toBe(422);
  expect(blocked.json().error.types).toEqual(["HEALTH"]);
  expect(upstream.requests).toHaveLength(1);
  await app.close();
});
