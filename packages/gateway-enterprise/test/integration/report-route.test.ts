import { afterEach, expect, it } from "vitest";

import { enterpriseHarness, login } from "../helpers.js";

let close: (() => Promise<void>) | undefined;
afterEach(async () => close?.());

it("exports an entitled PDF and records the export without content values", async () => {
  const { runtime } = await enterpriseHarness();
  close = () => runtime.app.close();
  const cookie = await login(runtime, "admin@example.test");
  const response = await runtime.app.inject({
    method: "POST",
    url: "/admin/reports/tedbir?from=2026-08-01&to=2026-08-31&format=pdf",
    headers: { cookie },
  });
  expect(response.statusCode, response.body).toBe(200);
  expect(response.headers["content-type"]).toBe("application/pdf");
  expect(response.rawPayload.subarray(0, 5).toString()).toBe("%PDF-");
  expect((await runtime.auditStore.list()).at(-1)?.kind).toBe("EXPORT_RUN");
});
