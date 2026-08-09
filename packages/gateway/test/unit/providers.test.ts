import { describe, expect, it } from "vitest";

import { GatewayError } from "../../src/errors.js";
import { AnthropicAdapter } from "../../src/providers/anthropic.js";
import { OpenAiAdapter } from "../../src/providers/openai.js";

describe("provider request field coverage", () => {
  it("collects OpenAI string, text-part, name, and tool-result content", () => {
    const parsed = new OpenAiAdapter().parseRequest({
      model: "test",
      messages: [
        { role: "system", name: "Ayşe", content: "system" },
        {
          role: "tool",
          content: [
            { type: "text", text: "text" },
            { type: "tool_result", content: "result" },
          ],
        },
      ],
    });
    expect(parsed.segments.map((segment) => segment.text)).toEqual([
      "system",
      "Ayşe",
      "text",
      "result",
    ]);
  });

  it("collects Anthropic system, text, and tool-result text", () => {
    const parsed = new AnthropicAdapter().parseRequest({
      model: "test",
      max_tokens: 32,
      system: "system",
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: "text" },
            { type: "tool_result", content: [{ type: "text", text: "result" }] },
          ],
        },
      ],
    });
    expect(parsed.segments.map((segment) => segment.text)).toEqual(["system", "text", "result"]);
  });

  it.each([new OpenAiAdapter(), new AnthropicAdapter()])(
    "blocks unknown multimodal parts",
    (adapter) => {
      const base = {
        model: "test",
        max_tokens: 32,
        messages: [{ role: "user", content: [{ type: "image", source: "x" }] }],
      };
      expect(() => adapter.parseRequest(base)).toThrow(GatewayError);
    },
  );
});
