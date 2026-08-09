import type { TextSegment } from "../mask/pipeline.js";

export interface ParsedProviderRequest {
  body: Record<string, unknown>;
  segments: TextSegment[];
  stream: boolean;
}

export interface StreamField {
  key: string;
  text: string;
  set(value: string): void;
  make(value: string): Record<string, unknown>;
}

export interface ProviderAdapter {
  readonly kind: "openai" | "anthropic";
  parseRequest(input: unknown): ParsedProviderRequest;
  unmaskResponse(
    input: unknown,
    resolveText: (text: string) => Promise<string>,
  ): Promise<Record<string, unknown>>;
  responseSegments(input: Record<string, unknown>): TextSegment[];
  streamFields(payload: Record<string, unknown>): StreamField[];
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
