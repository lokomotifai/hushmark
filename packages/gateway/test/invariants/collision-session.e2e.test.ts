import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

const SESSION = "019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21";

it("rejects placeholder collisions by default", async () => {
  const upstream = new FakeUpstream();
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  const response = await request(app, "[KISI_1] Ayşe Yılmaz");
  expect(response.statusCode).toBe(422);
  expect(response.json().error.code).toBe("HM-4102");
  expect(upstream.requests).toHaveLength(0);
  await app.close();
});

it("prefix mode and session continuity issue stable placeholders", async () => {
  const upstream = new FakeUpstream();
  const policy = testPolicy({
    defaults: {
      unknown_entity: "block",
      multimodal: "block",
      collision_mode: "prefix",
      response_scan: "off",
    },
  });
  const app = buildServer({ config: testConfig(), policy, core: new FakeCore(), upstream });
  expect((await request(app, "[KISI_1] Ayşe Yılmaz")).statusCode).toBe(200);
  expect((await request(app, "Ayşe Yılmaz")).statusCode).toBe(200);
  const bodies = upstream.requests.map((entry) => JSON.stringify(entry.body));
  expect(bodies[0]).toContain("[KISI_1]#abcdabcdabcdabcd");
  expect(bodies[1]).toContain("[KISI_1]#abcdabcdabcdabcd");
  await app.close();
});

async function request(app: ReturnType<typeof buildServer>, content: string) {
  return app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}`, "x-hushmark-session": SESSION },
    payload: { model: "test", messages: [{ role: "user", content }] },
  });
}
