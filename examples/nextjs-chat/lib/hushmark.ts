import { createOpenAI } from "@ai-sdk/openai";
import { createHushmark } from "@hushmark/ai-sdk";
import { wrapLanguageModel, type LanguageModel } from "ai";

export function localModel(): LanguageModel {
  const apiKey = requiredEnv("HUSHMARK_API_KEY");
  const hushmark = createHushmark({
    baseUrl: process.env.HUSHMARK_GATEWAY_URL ?? "http://127.0.0.1:8080",
    apiKey,
  });
  const provider = createOpenAI({
    baseURL: hushmark.openaiBaseUrl,
    apiKey,
    fetch: hushmark.fetch,
  });
  return wrapLanguageModel({
    model: provider.chat(process.env.HUSHMARK_EXAMPLE_MODEL ?? "test"),
    middleware: hushmark.middleware(),
  });
}

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) throw new Error(`${name} is required`);
  return value;
}
