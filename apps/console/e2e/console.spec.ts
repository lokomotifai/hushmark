import { expect, test } from "@playwright/test";

import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  API_KEY,
  DEMO_TEXT,
  GATEWAY_URL,
  startEnterpriseStack,
} from "./stack";

let close: (() => Promise<void>) | undefined;

test.beforeAll(async () => {
  const runtime = await startEnterpriseStack();
  close = () => runtime.app.close();
});

test.afterAll(async () => close?.());

test("login, policy edit, traffic audit, verification, and PDF export", async ({
  page,
  request,
}) => {
  await page.goto("/login");
  await page.getByLabel("E-posta").fill(ADMIN_EMAIL);
  await page.getByLabel("Parola").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await expect(page).toHaveURL(/\/dashboard$/u);
  await expect(page.getByRole("heading", { name: "Teknik tedbir özeti" })).toBeVisible();

  await page.goto("/policies");
  await page.getByLabel("Politika adı").fill("E2E Ana Politika");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await expect(page.getByText("Politika kaydedildi")).toBeVisible();

  const traffic = await request.post(`${GATEWAY_URL}/v1/chat/completions`, {
    headers: { authorization: `Bearer ${API_KEY}` },
    data: { model: "test", messages: [{ role: "user", content: DEMO_TEXT }] },
  });
  expect(traffic.status()).toBe(200);
  expect(await traffic.text()).toContain("Ayşe Yılmaz");

  await page.goto("/audit");
  await expect(page.getByText("MASK_APPLIED")).toBeVisible();
  await page.getByRole("button", { name: "Zinciri doğrula" }).click();
  await expect(page.getByText(/kayıt doğrulandı/u)).toBeVisible();

  await page.goto("/reports");
  await page.getByLabel("Başlangıç").fill("2026-08-01");
  await page.getByLabel("Bitiş").fill("2026-08-31");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "PDF raporunu indir" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("hushmark-tedbir-2026-08-01-2026-08-31.pdf");
});
