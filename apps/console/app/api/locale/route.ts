import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";

const LocaleSchema = z.object({ locale: z.enum(["tr", "en"]) }).strict();

export async function POST(request: NextRequest): Promise<NextResponse> {
  const { locale } = LocaleSchema.parse(await request.json());
  const response = NextResponse.json({ locale });
  response.cookies.set("hm_locale", locale, {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    maxAge: 31_536_000,
  });
  return response;
}
