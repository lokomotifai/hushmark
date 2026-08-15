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

it("forwards only the admin cookie in both directions", async () => {
  const upstreamHeaders = new Headers();
  upstreamHeaders.append("set-cookie", "hm_admin=one; Path=/; HttpOnly");
  upstreamHeaders.append("set-cookie", "hm_locale=tr; Path=/");
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response("{}", {
      status: 200,
      headers: upstreamHeaders,
    }),
  );
  vi.stubGlobal("fetch", fetchSpy);
  const response = await POST(
    new NextRequest("http://console.test/api/admin/auth/login", {
      method: "POST",
      headers: {
        cookie: "hm_admin=session-secret; hm_locale=tr; unrelated=value",
        host: "console.test",
        origin: "http://console.test",
      },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["auth", "login"] }) },
  );
  expect(response.headers.getSetCookie()).toEqual(["hm_admin=one; Path=/; HttpOnly"]);
  const upstreamRequest = fetchSpy.mock.calls[0]?.[1] as RequestInit;
  expect(new Headers(upstreamRequest.headers).get("cookie")).toBe("hm_admin=session-secret");
});

it("does not trust forwarded host headers for CSRF validation", async () => {
  const fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
  const response = await POST(
    new NextRequest("http://console.test/api/admin/auth/login", {
      method: "POST",
      headers: {
        host: "console.test",
        origin: "https://attacker.test",
        "x-forwarded-host": "attacker.test",
        "x-forwarded-proto": "https",
      },
      body: "{}",
    }),
    { params: Promise.resolve({ path: ["auth", "login"] }) },
  );
  expect(response.status).toBe(403);
  expect(fetchSpy).not.toHaveBeenCalled();
});
