import type { ProviderAdapter, StreamField } from "../providers/types.js";
import { isRecord } from "../providers/types.js";
import { unmaskJsonDocument } from "../providers/content.js";
import type { VaultScope, VaultStore } from "../vault/memory.js";
import { StreamingUnmasker, type UnmaskAuthorization, unmaskText } from "./unmasker.js";

interface StreamState {
  unmasker: StreamingUnmasker;
  make: (value: string) => Record<string, unknown>;
  format: "text" | "json";
  jsonBuffer: string;
}

export async function* transformSse(
  source: AsyncIterable<Uint8Array>,
  adapter: ProviderAdapter,
  scope: VaultScope,
  vault: VaultStore,
  authorization: UnmaskAuthorization,
): AsyncGenerator<string> {
  const decoder = new TextDecoder();
  const states = new Map<string, StreamState>();
  let pending = "";

  const flushStates = async (): Promise<string> => {
    let output = "";
    for (const state of states.values()) {
      if (state.format === "json") {
        if (state.jsonBuffer.length === 0) continue;
        const restored = await unmaskJsonDocument(state.jsonBuffer, (text) =>
          unmaskText(text, scope, vault, authorization),
        );
        output += `data: ${JSON.stringify(state.make(restored))}\n\n`;
      } else {
        const tail = await state.unmasker.finish();
        if (tail.length > 0) output += `data: ${JSON.stringify(state.make(tail))}\n\n`;
      }
    }
    states.clear();
    return output;
  };

  const processFrame = async (frame: string, separator: string): Promise<string> => {
    const newline = frame.includes("\r\n") ? "\r\n" : "\n";
    const lines = frame.split(/\r?\n/u);
    const dataIndex = lines.findIndex((line) => line.startsWith("data:"));
    if (dataIndex < 0) return frame + separator;
    const dataMatch = /^(data:\s?)(.*)$/u.exec(lines[dataIndex] ?? "");
    if (dataMatch === null) return frame + separator;
    const data = dataMatch[2] ?? "";
    if (data === "[DONE]") return (await flushStates()) + frame + separator;
    let parsed: unknown;
    try {
      parsed = JSON.parse(data);
    } catch {
      return frame + separator;
    }
    if (!isRecord(parsed)) return frame + separator;
    const terminal = parsed.type === "message_stop";
    if (terminal) return (await flushStates()) + frame + separator;
    const fields = adapter.streamFields(parsed);
    for (const field of fields) {
      const state = stateFor(field, states, scope, vault, authorization);
      if (state.format === "json") {
        state.jsonBuffer += field.text;
        field.set("");
      } else {
        field.set(await state.unmasker.push(field.text));
      }
      state.make = (value) => field.make(value);
    }
    const dataPrefix = dataMatch[1] ?? "data: ";
    lines[dataIndex] = `${dataPrefix}${JSON.stringify(parsed)}`;
    return lines.join(newline) + separator;
  };

  for await (const chunk of source) {
    pending += decoder.decode(chunk, { stream: true });
    for (;;) {
      const delimiter = /\r?\n\r?\n/u.exec(pending);
      if (delimiter === null) break;
      const frame = pending.slice(0, delimiter.index);
      pending = pending.slice(delimiter.index + delimiter[0].length);
      yield await processFrame(frame, delimiter[0]);
    }
  }
  pending += decoder.decode();
  if (pending.length > 0) yield await processFrame(pending, "");
  yield await flushStates();
}

function stateFor(
  field: StreamField,
  states: Map<string, StreamState>,
  scope: VaultScope,
  vault: VaultStore,
  authorization: UnmaskAuthorization,
): StreamState {
  const existing = states.get(field.key);
  if (existing !== undefined) return existing;
  const created: StreamState = {
    unmasker: new StreamingUnmasker(scope, vault, authorization),
    make: (value: string) => field.make(value),
    format: field.format ?? "text",
    jsonBuffer: "",
  };
  states.set(field.key, created);
  return created;
}
