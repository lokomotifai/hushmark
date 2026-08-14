import { z } from "zod";

import { GatewayError } from "../errors.js";
import type { TextSegment } from "../mask/pipeline.js";
import { collectContent, collectJsonStrings, unmaskContent } from "./content.js";
import type { ParsedProviderRequest, ProviderAdapter, StreamField } from "./types.js";
import { isRecord } from "./types.js";

const RequestSchema = z
  .object({
    model: z.string().min(1),
    max_tokens: z.number().int().positive(),
    stream: z.boolean().optional().default(false),
    system: z.unknown().optional(),
    messages: z.array(z.record(z.string(), z.unknown())).min(1),
    metadata: z.unknown().optional(),
    service_tier: z.unknown().optional(),
    stop_sequences: z.unknown().optional(),
    temperature: z.unknown().optional(),
    thinking: z.unknown().optional(),
    tool_choice: z.unknown().optional(),
    tools: z.unknown().optional(),
    top_k: z.unknown().optional(),
    top_p: z.unknown().optional(),
  })
  .strict();

export class AnthropicAdapter implements ProviderAdapter {
  readonly kind = "anthropic" as const;

  parseRequest(input: unknown): ParsedProviderRequest {
    const parsed = RequestSchema.safeParse(input);
    if (!parsed.success) throw new GatewayError("HM-4001", "malformed request");
    const body = structuredClone(parsed.data) as Record<string, unknown>;
    const segments: TextSegment[] = [];
    if (body.system !== undefined) {
      collectContent(
        body.system,
        "system",
        (value) => {
          body.system = value;
        },
        segments,
      );
    }
    if (!Array.isArray(body.messages)) throw new GatewayError("HM-4001", "malformed request");
    body.messages.forEach((message, index) => {
      if (!isRecord(message) || typeof message.role !== "string" || !("content" in message)) {
        throw new GatewayError("HM-4001", "malformed request");
      }
      collectContent(
        message.content,
        `message.${String(index)}.content`,
        (value) => {
          message.content = value;
        },
        segments,
      );
    });
    for (const field of ["metadata", "stop_sequences", "thinking", "tools"] as const) {
      if (!(field in body)) continue;
      collectJsonStrings(body[field], `request.${field}`, segments, (value) => {
        body[field] = value;
      });
    }
    return { body, segments, stream: parsed.data.stream };
  }

  async unmaskResponse(
    input: unknown,
    resolveText: (text: string) => Promise<string>,
  ): Promise<Record<string, unknown>> {
    if (!isRecord(input) || !Array.isArray(input.content)) {
      throw new GatewayError("HM-5001", "upstream provider error");
    }
    const body = structuredClone(input);
    await unmaskContent(body.content, resolveText);
    return body;
  }

  responseSegments(input: Record<string, unknown>): TextSegment[] {
    if (!Array.isArray(input.content)) return [];
    const segments: TextSegment[] = [];
    collectContent(
      input.content,
      "response.content",
      (value) => {
        input.content = value;
      },
      segments,
    );
    return segments;
  }

  streamFields(payload: Record<string, unknown>): StreamField[] {
    if (!isRecord(payload.delta) || typeof payload.index !== "number") return [];
    const delta = payload.delta;
    if (delta.type === "text_delta" && typeof delta.text === "string") {
      return [
        {
          key: `block.${String(payload.index)}.text`,
          text: delta.text,
          set: (value) => {
            delta.text = value;
          },
          make: (value) => ({
            type: "content_block_delta",
            index: payload.index,
            delta: { type: "text_delta", text: value },
          }),
        },
      ];
    }
    if (delta.type === "input_json_delta" && typeof delta.partial_json === "string") {
      return [
        {
          key: `block.${String(payload.index)}.input`,
          text: delta.partial_json,
          format: "json",
          set: (value) => {
            delta.partial_json = value;
          },
          make: (value) => ({
            type: "content_block_delta",
            index: payload.index,
            delta: { type: "input_json_delta", partial_json: value },
          }),
        },
      ];
    }
    return [];
  }
}
