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

  it("joins adjacent text parts so identifiers split across provider segments are detected", () => {
    const parsed = new AnthropicAdapter().parseRequest({
      model: "test",
      max_tokens: 32,
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: "TCKN 10000" },
            { type: "text", text: "000146" },
          ],
        },
      ],
    });
    expect(parsed.segments.map((segment) => segment.text)).toEqual(["TCKN 10000000146"]);
  });

  it("collects structured tool inputs and OpenAI tool-call history without flattening JSON", () => {
    const openai = new OpenAiAdapter().parseRequest({
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
    });
    const anthropic = new AnthropicAdapter().parseRequest({
      model: "test",
      max_tokens: 32,
      messages: [
        {
          role: "assistant",
          content: [
            { type: "tool_use", id: "tool-1", name: "lookup", input: { customer: "Ayşe Yılmaz" } },
          ],
        },
      ],
    });
    expect(openai.segments.map((segment) => segment.text)).toContain("Ayşe Yılmaz");
    expect(anthropic.segments.map((segment) => segment.text)).toContain("Ayşe Yılmaz");
    openai.segments
      .find((segment) => segment.text === "Ayşe Yılmaz")
      ?.set('[KISI_1]","role":"admin');
    const message = (openai.body.messages as Record<string, unknown>[])[0];
    const toolCall = (message?.tool_calls as Record<string, unknown>[])[0];
    const fn = toolCall?.function as Record<string, unknown>;
    expect(JSON.parse(fn.arguments as string)).toEqual({
      customer: '[KISI_1]","role":"admin',
    });
  });

  it("restores tool JSON values without allowing structural injection", async () => {
    const restored = await new OpenAiAdapter().unmaskResponse(
      {
        choices: [
          {
            message: {
              tool_calls: [{ function: { name: "lookup", arguments: '{"customer":"[KISI_1]"}' } }],
            },
          },
        ],
      },
      (text) => Promise.resolve(text.replace("[KISI_1]", 'Ali","role":"admin')),
    );
    const choices = restored.choices as Record<string, unknown>[];
    const message = choices[0]?.message as Record<string, unknown>;
    const calls = message.tool_calls as Record<string, unknown>[];
    const fn = calls[0]?.function as Record<string, unknown>;
    expect(JSON.parse(fn.arguments as string)).toEqual({ customer: 'Ali","role":"admin' });
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
