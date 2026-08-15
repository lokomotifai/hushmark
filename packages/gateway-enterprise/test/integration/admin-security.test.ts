import { afterEach, expect, it } from "vitest";

import { ADMIN_PASSWORD, enterpriseHarness } from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("sets a Secure admin cookie", async () => {
  const { runtime } = await enterpriseHarness();
  close = () => runtime.app.close();
  const response = await runtime.app.inject({
    method: "POST",
    url: "/admin/auth/login",
    payload: { email: "admin@example.test", password: ADMIN_PASSWORD },
  });
  expect(response.statusCode, response.body).toBe(200);
  expect(response.headers["set-cookie"]).toContain("Secure");
  expect(response.headers["set-cookie"]).toContain("SameSite=Strict");
});

it("rate-limits repeated admin login attempts and records a pseudonymous actor", async () => {
  const { runtime } = await enterpriseHarness();
  close = () => runtime.app.close();
  const responses = [];
  for (let attempt = 0; attempt < 11; attempt += 1) {
    responses.push(
      await runtime.app.inject({
        method: "POST",
        url: "/admin/auth/login",
        headers: { "user-agent": "security-test" },
        payload: { email: "unknown@example.test", password: "wrong-password" },
      }),
    );
  }
  expect(responses.slice(0, 10).every((response) => response.statusCode === 401)).toBe(true);
  expect(responses[10]?.statusCode).toBe(429);
  expect(responses[10]?.json()).toMatchObject({ error: { code: "HM-4290" } });
  const events = await runtime.auditStore.list();
  expect(events.at(-1)?.actor).toMatch(/^anonymous:[0-9a-f]{16}$/u);
});
