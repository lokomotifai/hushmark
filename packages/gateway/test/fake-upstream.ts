import type { UpstreamPort, UpstreamResponse } from "../src/upstream.js";

export class FakeUpstream implements UpstreamPort {
  readonly requests: { kind: "openai" | "anthropic"; body: Record<string, unknown> }[] = [];
  responseOverride: string | undefined;

  async forward(
    kind: "openai" | "anthropic",
    body: Record<string, unknown>,
  ): Promise<UpstreamResponse> {
    this.requests.push({ kind, body: structuredClone(body) });
    const text = this.responseOverride ?? requestText(kind, body);
    if (body.stream === true) return streamResponse(kind, text);
    const response =
      kind === "openai"
        ? {
            id: "chatcmpl-test",
            choices: [{ index: 0, message: { role: "assistant", content: text } }],
          }
        : { id: "msg-test", type: "message", content: [{ type: "text", text }] };
    return jsonResponse(response);
  }
}

function requestText(kind: "openai" | "anthropic", body: Record<string, unknown>): string {
  const messages = body.messages;
  if (!Array.isArray(messages)) return "";
  const last = messages.at(-1);
  if (typeof last !== "object" || last === null || !("content" in last)) return "";
  const content = last.content;
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) =>
      typeof part === "object" && part !== null && "text" in part && typeof part.text === "string"
        ? part.text
        : "",
    )
    .join("");
}

function streamResponse(kind: "openai" | "anthropic", text: string): UpstreamResponse {
  const slices = [...text].map((character) => character);
  const frames = slices.map((character, index) => {
    const payload =
      kind === "openai"
        ? { choices: [{ index: 0, delta: { content: character } }] }
        : {
            type: "content_block_delta",
            index: 0,
            delta: { type: "text_delta", text: character },
          };
    return `data: ${JSON.stringify(payload)}\n\n${index % 5 === 0 ? ": heartbeat\n\n" : ""}`;
  });
  frames.push(
    kind === "openai"
      ? "data: [DONE]\n\n"
      : 'event: message_stop\ndata: {"type":"message_stop"}\n\n',
  );
  return iterableResponse(frames);
}

function jsonResponse(value: Record<string, unknown>): UpstreamResponse {
  const serialized = JSON.stringify(value);
  return iterableResponse([serialized], value);
}

function iterableResponse(chunks: string[], jsonValue?: Record<string, unknown>): UpstreamResponse {
  const body = {
    async *[Symbol.asyncIterator]() {
      for (const chunk of chunks) yield new TextEncoder().encode(chunk);
    },
    async json() {
      if (jsonValue === undefined) throw new Error("not JSON");
      return structuredClone(jsonValue);
    },
    async text() {
      return chunks.join("");
    },
  };
  return {
    statusCode: 200,
    headers: { "content-type": jsonValue === undefined ? "text/event-stream" : "application/json" },
    body,
  };
}
