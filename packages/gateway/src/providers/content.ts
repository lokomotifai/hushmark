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
  if (content === null) return;
  if (typeof content === "string") {
    segments.push({ id: idPrefix, text: content, set: (value) => assign(value) });
    return;
  }
  if (!Array.isArray(content)) {
    throw new GatewayError("HM-4203", "unsupported content part");
  }
  const parts = content as unknown[];
  for (let index = 0; index < parts.length; index += 1) {
    const part: unknown = parts[index];
    if (!isRecord(part) || typeof part.type !== "string" || !ALLOWED_PARTS.has(part.type)) {
      throw new GatewayError("HM-4203", "unsupported content part");
    }
    if (part.type === "text") {
      const textParts: Record<string, unknown>[] = [];
      let cursor = index;
      while (cursor < parts.length) {
        const candidate: unknown = parts[cursor];
        if (!isRecord(candidate) || candidate.type !== "text") break;
        if (typeof candidate.text !== "string") {
          throw new GatewayError("HM-4203", "unsupported content part");
        }
        textParts.push(candidate);
        cursor += 1;
      }
      segments.push({
        id: `${idPrefix}.part.${String(index)}`,
        text: textParts.map((candidate) => candidate.text).join(""),
        set: (value) => {
          const first = textParts[0];
          if (first !== undefined) first.text = value;
          for (const remainder of textParts.slice(1)) remainder.text = "";
        },
      });
      index = cursor - 1;
      continue;
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
    if (part.type === "tool_use" && isRecord(part.input)) {
      collectJsonStrings(part.input, `${idPrefix}.tool_use.${String(index)}`, segments);
    }
  }
}

export function collectJsonStrings(
  value: unknown,
  idPrefix: string,
  segments: TextSegment[],
  assign?: (value: unknown) => void,
): void {
  if (typeof value === "string") {
    if (assign === undefined) return;
    segments.push({ id: idPrefix, text: value, set: assign });
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) =>
      collectJsonStrings(item, `${idPrefix}.${String(index)}`, segments, (replacement) => {
        value[index] = replacement;
      }),
    );
    return;
  }
  if (!isRecord(value)) return;
  for (const [key, item] of Object.entries(value)) {
    collectJsonStrings(item, `${idPrefix}.${key}`, segments, (replacement) => {
      value[key] = replacement;
    });
  }
}

export function collectJsonDocument(
  document: string,
  idPrefix: string,
  segments: TextSegment[],
  assign: (value: string) => void,
): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(document) as unknown;
  } catch {
    throw new GatewayError("HM-4203", "tool arguments must be valid JSON");
  }
  const start = segments.length;
  collectJsonStrings(parsed, idPrefix, segments, (replacement) => {
    parsed = replacement;
  });
  for (const segment of segments.slice(start)) {
    const originalSet = segment.set;
    segment.set = (value) => {
      originalSet(value);
      assign(JSON.stringify(parsed));
    };
  }
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
      part.input = await unmaskJsonValue(part.input, resolveText);
    }
  }
}

export async function unmaskJsonValue(
  value: unknown,
  resolveText: (text: string) => Promise<string>,
): Promise<unknown> {
  if (typeof value === "string") return resolveText(value);
  if (Array.isArray(value)) {
    return Promise.all(value.map((item) => unmaskJsonValue(item, resolveText)));
  }
  if (!isRecord(value)) return value;
  const output: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    output[key] = await unmaskJsonValue(item, resolveText);
  }
  return output;
}

export async function unmaskJsonDocument(
  document: string,
  resolveText: (text: string) => Promise<string>,
): Promise<string> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(document) as unknown;
  } catch {
    throw new GatewayError("HM-5001", "upstream tool arguments are not valid JSON");
  }
  return JSON.stringify(await unmaskJsonValue(parsed, resolveText));
}
