import { expect, it } from "vitest";

import { buildServer } from "../../src/server.js";
import { MemoryVault, type VaultEvent } from "../../src/vault/memory.js";
import { FakeUpstream } from "../fake-upstream.js";
import { API_KEY, FakeCore, testConfig, testPolicy } from "../helpers.js";

it("INV-01 structured gateway events contain no raw values", async () => {
  const events: VaultEvent[] = [];
  const vault = new MemoryVault(1, Date.now, (event) => events.push(event));
  const app = buildServer({
    config: testConfig(),
    policy: testPolicy(),
    core: new FakeCore(),
    upstream: new FakeUpstream(),
    vault,
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
  const serialized = JSON.stringify(events);
  expect(serialized).not.toContain("Ayşe Yılmaz");
  expect(serialized).not.toContain("10000000146");
  await app.close();
});
