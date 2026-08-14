import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";

import { POST } from "../app/api/admin/[...path]/route.js";

afterEach(() => vi.unstubAllGlobals());

it("rejects cross-origin admin mutations before proxying", async () => {
  const fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
  const response = await POST(
    new NextRequest("http://console.test/api/admin/auth/login", {
      method: "POST",
      headers: { host: "console.test", origin: "https://attacker.test" },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["auth", "login"] }) },
  );
  expect(response.status).toBe(403);
  expect(fetchSpy).not.toHaveBeenCalled();
});

it("preserves separate Set-Cookie headers from the gateway", async () => {
  const upstreamHeaders = new Headers();
  upstreamHeaders.append("set-cookie", "hm_admin=one; Path=/; HttpOnly");
  upstreamHeaders.append("set-cookie", "hm_locale=tr; Path=/");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response("{}", {
        status: 200,
        headers: upstreamHeaders,
      }),
    ),
  );
  const response = await POST(
    new NextRequest("http://console.test/api/admin/auth/login", {
      method: "POST",
      headers: { host: "console.test", origin: "http://console.test" },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["auth", "login"] }) },
  );
  expect(response.headers.getSetCookie()).toEqual([
    "hm_admin=one; Path=/; HttpOnly",
    "hm_locale=tr; Path=/",
  ]);
});
