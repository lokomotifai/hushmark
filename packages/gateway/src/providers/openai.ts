import { z } from "zod";

import { GatewayError } from "../errors.js";
import type { TextSegment } from "../mask/pipeline.js";
import { collectContent, unmaskContent } from "./content.js";
import type { ParsedProviderRequest, ProviderAdapter, StreamField } from "./types.js";
import { isRecord } from "./types.js";

const RequestSchema = z
  .object({
    model: z.string().min(1),
    stream: z.boolean().optional().default(false),
    messages: z.array(z.record(z.string(), z.unknown())).min(1),
  })
  .loose();

export class OpenAiAdapter implements ProviderAdapter {
  readonly kind = "openai" as const;

  parseRequest(input: unknown): ParsedProviderRequest {
    const parsed = RequestSchema.safeParse(input);
    if (!parsed.success) throw new GatewayError("HM-4001", "malformed request");
    const body = structuredClone(parsed.data) as Record<string, unknown>;
    const messages = body.messages;
    if (!Array.isArray(messages)) throw new GatewayError("HM-4001", "malformed request");
    const segments: TextSegment[] = [];
    messages.forEach((message, index) => {
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
      if (typeof message.name === "string") {
        segments.push({
          id: `message.${String(index)}.name`,
          text: message.name,
          set: (value) => {
            message.name = value;
          },
        });
      }
    });
    return { body, segments, stream: parsed.data.stream };
  }

  async unmaskResponse(
    input: unknown,
    resolveText: (text: string) => Promise<string>,
  ): Promise<Record<string, unknown>> {
    if (!isRecord(input) || !Array.isArray(input.choices)) {
      throw new GatewayError("HM-5001", "upstream provider error");
    }
    const body = structuredClone(input);
    const choices = body.choices;
    if (!Array.isArray(choices)) throw new GatewayError("HM-5001", "upstream provider error");
    for (const choice of choices) {
      if (!isRecord(choice) || !isRecord(choice.message)) continue;
      const message = choice.message;
      if (typeof message.content === "string") message.content = await resolveText(message.content);
      await unmaskContent(message.content, resolveText);
      if (Array.isArray(message.tool_calls)) {
        for (const toolCall of message.tool_calls) {
          if (isRecord(toolCall) && isRecord(toolCall.function)) {
            const functionValue = toolCall.function;
            if (typeof functionValue.arguments === "string") {
              functionValue.arguments = await resolveText(functionValue.arguments);
            }
          }
        }
      }
    }
    return body;
  }

  responseSegments(input: Record<string, unknown>): TextSegment[] {
    if (!Array.isArray(input.choices)) return [];
    const segments: TextSegment[] = [];
    input.choices.forEach((choice, choiceIndex) => {
      if (!isRecord(choice) || !isRecord(choice.message)) return;
      const message = choice.message;
      if ("content" in message && message.content !== null) {
        collectContent(
          message.content,
          `response.${String(choiceIndex)}.content`,
          (value) => {
            message.content = value;
          },
          segments,
        );
      }
      if (!Array.isArray(message.tool_calls)) return;
      message.tool_calls.forEach((toolCall, toolIndex) => {
        if (!isRecord(toolCall) || !isRecord(toolCall.function)) return;
        const functionValue = toolCall.function;
        if (typeof functionValue.arguments !== "string") return;
        segments.push({
          id: `response.${String(choiceIndex)}.tool.${String(toolIndex)}`,
          text: functionValue.arguments,
          set: (value) => {
            functionValue.arguments = value;
          },
        });
      });
    });
    return segments;
  }

  streamFields(payload: Record<string, unknown>): StreamField[] {
    if (!Array.isArray(payload.choices)) return [];
    const fields: StreamField[] = [];
    payload.choices.forEach((choice, choiceIndex) => {
      if (!isRecord(choice) || !isRecord(choice.delta)) return;
      const delta = choice.delta;
      if (typeof delta.content === "string") {
        fields.push({
          key: `choice.${String(choiceIndex)}.content`,
          text: delta.content,
          set: (value) => {
            delta.content = value;
          },
          make: (value) => ({
            ...payload,
            choices: [{ index: choiceIndex, delta: { content: value } }],
          }),
        });
      }
      if (!Array.isArray(delta.tool_calls)) return;
      delta.tool_calls.forEach((toolCall, toolIndex) => {
        if (!isRecord(toolCall) || !isRecord(toolCall.function)) return;
        const functionValue = toolCall.function;
        if (typeof functionValue.arguments !== "string") return;
        fields.push({
          key: `choice.${String(choiceIndex)}.tool.${String(toolIndex)}`,
          text: functionValue.arguments,
          set: (value) => {
            functionValue.arguments = value;
          },
          make: (value) => ({
            ...payload,
            choices: [
              {
                index: choiceIndex,
                delta: { tool_calls: [{ index: toolIndex, function: { arguments: value } }] },
              },
            ],
          }),
        });
      });
    });
    return fields;
  }
}
