import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function PUT(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export function DELETE(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    const origin = request.headers.get("origin");
    if (origin === null || origin !== requestOrigin(request)) {
      return NextResponse.json(
        { error: { code: "HM-4030", message: "cross-origin admin request blocked" } },
        { status: 403 },
      );
    }
  }
  const { path } = await context.params;
  const gateway = new URL(process.env.HUSHMARK_GATEWAY_URL ?? "http://127.0.0.1:8080");
  gateway.pathname = `/admin/${path.map(encodeURIComponent).join("/")}`;
  gateway.search = request.nextUrl.search;
  const headers = new Headers();
  const adminCookie = request.cookies.get("hm_admin")?.value;
  const contentType = request.headers.get("content-type");
  if (adminCookie !== undefined) headers.set("cookie", `hm_admin=${adminCookie}`);
  if (contentType !== null) headers.set("content-type", contentType);
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const upstream = await fetch(gateway, {
    method: request.method,
    headers,
    ...(hasBody ? { body: await request.arrayBuffer() } : {}),
    cache: "no-store",
    redirect: "manual",
  });
  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase()) && key.toLowerCase() !== "set-cookie") {
      responseHeaders.set(key, value);
    }
  });
  for (const cookie of upstream.headers.getSetCookie()) {
    if (cookie.startsWith("hm_admin=")) responseHeaders.append("set-cookie", cookie);
  }
  return new NextResponse(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: responseHeaders,
  });
}

function requestOrigin(request: NextRequest): string | null {
  const configured = process.env.HUSHMARK_CONSOLE_ORIGIN;
  try {
    return configured === undefined ? request.nextUrl.origin : new URL(configured).origin;
  } catch {
    return null;
  }
}
