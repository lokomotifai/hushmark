import { GatewayError } from "../errors.js";
import type { TextSegment } from "../mask/pipeline.js";
import { isRecord } from "./types.js";

const ALLOWED_PARTS = new Set(["text", "tool_result", "tool_use"]);

export function collectContent(
  content: unknown,
  idPrefix: string,
  assign: (value: unknown) => void,
  segments: TextSegment[],
): void {
  if (typeof content === "string") {
    segments.push({ id: idPrefix, text: content, set: (value) => assign(value) });
    return;
  }
  if (!Array.isArray(content)) {
    throw new GatewayError("HM-4203", "unsupported content part");
  }
  content.forEach((part, index) => {
    if (!isRecord(part) || typeof part.type !== "string" || !ALLOWED_PARTS.has(part.type)) {
      throw new GatewayError("HM-4203", "unsupported content part");
    }
    if (part.type === "text") {
      if (typeof part.text !== "string") {
        throw new GatewayError("HM-4203", "unsupported content part");
      }
      segments.push({
        id: `${idPrefix}.part.${String(index)}`,
        text: part.text,
        set: (value) => {
          part.text = value;
        },
      });
    }
    if (part.type === "tool_result") {
      collectContent(
        part.content,
        `${idPrefix}.tool_result.${String(index)}`,
        (value) => {
          part.content = value;
        },
        segments,
      );
    }
  });
}

export async function unmaskContent(
  content: unknown,
  resolveText: (text: string) => Promise<string>,
): Promise<void> {
  if (!Array.isArray(content)) return;
  for (const part of content) {
    if (!isRecord(part)) continue;
    if (typeof part.text === "string") part.text = await resolveText(part.text);
    if (typeof part.content === "string") part.content = await resolveText(part.content);
    if (part.type === "tool_use" && isRecord(part.input)) {
      const serialized = JSON.stringify(part.input);
      part.input = JSON.parse(await resolveText(serialized)) as unknown;
    }
  }
}
