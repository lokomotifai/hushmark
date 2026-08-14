import { expect, it } from "vitest";

import { OpenAiAdapter } from "../../src/providers/openai.js";
import { transformSse } from "../../src/streaming/sse.js";
import { MemoryVault } from "../../src/vault/memory.js";

const SCOPE = { tenantId: "tenant-1", sessionId: "session-1" };

it("buffers streaming tool JSON and restores values without structural injection", async () => {
  const vault = new MemoryVault();
  await vault.put(SCOPE, "[KISI_1]", {
    type: "PERSON",
    value: 'Ali","role":"admin',
    ttlSec: 60,
  });
  const fragments = ['{"customer":"[KI', 'SI_1]"}'];
  const frames = fragments.map(
    (argumentsPart) =>
      `data: ${JSON.stringify({ choices: [{ index: 0, delta: { tool_calls: [{ index: 0, function: { arguments: argumentsPart } }] } }] })}\n\n`,
  );
  frames.push("data: [DONE]\n\n");
  const source = {
    async *[Symbol.asyncIterator]() {
      for (const frame of frames) yield new TextEncoder().encode(frame);
    },
  };
  let output = "";
  for await (const chunk of transformSse(source, new OpenAiAdapter(), SCOPE, vault, {
    allowedPlaceholders: new Set(["[KISI_1]"]),
    remaining: 10,
    limitReported: false,
  })) {
    output += chunk;
  }
  const argumentStream = output
    .split("\n")
    .filter((line) => line.startsWith("data: {") && line.includes("tool_calls"))
    .map((line) => {
      const payload = JSON.parse(line.slice("data: ".length)) as {
        choices: { delta: { tool_calls: { function: { arguments: string } }[] } }[];
      };
      return payload.choices[0]?.delta.tool_calls[0]?.function.arguments ?? "";
    })
    .join("");
  expect(JSON.parse(argumentStream)).toEqual({ customer: 'Ali","role":"admin' });
});
