import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { FakeUpstream } from "../fake-upstream.js";
import type { MaskRequest, MaskResponse } from "@hushmark/shared";

import type { CorePort } from "../../src/coreClient.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("INV-09 blocks an unknown provider content part", async () => {
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
      messages: [{ role: "user", content: [{ type: "image_url", image_url: "secret" }] }],
    },
  });
  expect(response.statusCode).toBe(422);
  expect(response.json()).toEqual({
    error: { code: "HM-4203", message: "unsupported content part" },
  });
  expect(upstream.requests).toHaveLength(0);
  await app.close();
});

it("INV-09 blocks a core-emitted type outside the closed taxonomy", async () => {
  const upstream = new FakeUpstream();
  const rogueCore: CorePort = {
    async mask(request: MaskRequest): Promise<MaskResponse> {
      return {
        items: request.items.map((item) => ({
          id: item.id,
          masked_text: "[ROGUE_1]",
          mappings: [
            {
              placeholder: "[ROGUE_1]",
              type: "ROGUE",
              start: 0,
              end: item.text.length,
              value: item.text,
              confidence: 1,
              layer: "ner",
            },
          ],
        })),
        model_id: "rogue",
        taxonomy_version: "1",
      } as unknown as MaskResponse;
    },
  };
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: rogueCore,
    upstream,
  });
  const response = await app.inject({
    method: "POST",
    url: "/v1/chat/completions",
    headers: { authorization: `Bearer ${API_KEY}` },
    payload: { model: "test", messages: [{ role: "user", content: "canary" }] },
  });
  expect(response.statusCode).toBe(422);
  expect(response.json().error.code).toBe("HM-4201");
  expect(upstream.requests).toHaveLength(0);
  await app.close();
});
