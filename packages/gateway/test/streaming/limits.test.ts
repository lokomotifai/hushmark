import { expect, it } from "vitest";

import { OpenAiAdapter } from "../../src/providers/openai.js";
import { transformSse } from "../../src/streaming/sse.js";
import { MemoryVault } from "../../src/vault/memory.js";

const SCOPE = { tenantId: "tenant-1", sessionId: "session-1" };
const AUTHORIZATION = {
  allowedPlaceholders: new Set<string>(),
  remaining: 10,
  limitReported: false,
};

it("rejects an SSE provider that never terminates a frame", async () => {
  const source = chunks(["data: " + "x".repeat(32)]);
  const consume = async () => {
    for await (const chunk of transformSse(
      source,
      new OpenAiAdapter(),
      SCOPE,
      new MemoryVault(),
      { ...AUTHORIZATION },
      { maxBufferBytes: 16, maxStates: 2 },
    )) {
      // Consume the stream to force the bounded parser to run.
      void chunk;
    }
  };
  await expect(consume()).rejects.toMatchObject({ code: "HM-5001" });
});

it("rejects more simultaneous stream states than configured", async () => {
  const frame = `data: ${JSON.stringify({
    choices: [
      { index: 0, delta: { content: "one" } },
      { index: 1, delta: { content: "two" } },
    ],
  })}\n\n`;
  const consume = async () => {
    for await (const chunk of transformSse(
      chunks([frame]),
      new OpenAiAdapter(),
      SCOPE,
      new MemoryVault(),
      { ...AUTHORIZATION },
      { maxBufferBytes: 1_024, maxStates: 1 },
    )) {
      // Consume the stream to force state creation.
      void chunk;
    }
  };
  await expect(consume()).rejects.toMatchObject({ code: "HM-5001" });
});

function chunks(values: readonly string[]): AsyncIterable<Uint8Array> {
  return {
    async *[Symbol.asyncIterator]() {
      for (const value of values) yield new TextEncoder().encode(value);
    },
  };
}
