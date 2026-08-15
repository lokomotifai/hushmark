import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

const SESSION = "019121aa-7c3e-7bbb-9a10-3f6e2b4c9d21";

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

it("only restores placeholders issued by the current request", async () => {
  const upstream = new FakeUpstream();
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  const headers = {
    authorization: `Bearer ${API_KEY}`,
    "x-hushmark-session": SESSION,
  };
  expect(
    (
      await app.inject({
        method: "POST",
        url: "/v1/chat/completions",
        headers,
        payload: { model: "test", messages: [{ role: "user", content: "Ayşe Yılmaz" }] },
      })
    ).body,
  ).toContain("Ayşe Yılmaz");

  upstream.responseOverride = "Guessed: [KISI_1]";
  const guessed = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers,
    payload: { model: "test", messages: [{ role: "user", content: "Merhaba" }] },
  });
  expect(guessed.body).toContain("[KISI_1]");
  expect(guessed.body).not.toContain("Ayşe Yılmaz");
  await app.close();
});

it("never forwards PII from OpenAI tool-call history", async () => {
  const upstream = new FakeUpstream();
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream,
  });
  const response = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: {
      model: "test",
      messages: [
        {
          role: "assistant",
          content: null,
          tool_calls: [
            {
              id: "call-1",
              type: "function",
              function: { name: "lookup", arguments: '{"customer":"Ayşe Yılmaz"}' },
            },
          ],
        },
      ],
    },
  });
  expect(response.statusCode, response.body).toBe(200);
  const forwarded = JSON.stringify(upstream.requests);
  expect(forwarded).not.toContain("Ayşe Yılmaz");
  expect(forwarded).toContain("[KISI_1]");
  await app.close();
});
