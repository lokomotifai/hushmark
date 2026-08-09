import { generateText } from "ai";
import { z } from "zod";

import { localModel } from "../../../lib/hushmark.js";

const RequestSchema = z.object({ message: z.string().min(1).max(8_000) }).strict();

export async function POST(request: Request): Promise<Response> {
  const parsed = RequestSchema.safeParse(await request.json());
  if (!parsed.success) return Response.json({ error: "Geçersiz istek" }, { status: 400 });
  const result = await generateText({ model: localModel(), prompt: parsed.data.message });
  return Response.json({ answer: result.text });
}
