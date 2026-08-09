import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("INV-12 emits unresolved placeholders unchanged after an in-memory restart", async () => {
  const upstream = new FakeUpstream();
  upstream.responseOverride = "[KISI_1]";
  const restarted = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  const response = await restarted.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: "placeholder yok" }] },
  });
  expect(response.statusCode).toBe(200);
  expect(response.body).toContain("[KISI_1]");
  await restarted.close();
});
