import { PDFParse } from "pdf-parse";
import { expect, it } from "vitest";

import { sha256 } from "../../src/audit/canonical.js";
import { MemoryAuditCheckpointStore } from "../../src/audit/checkpoint.js";
import { MemoryAuditStore } from "../../src/audit/store.js";
import { AuditWriter } from "../../src/audit/writer.js";
import { buildTedbirReportData, renderTedbirPdf } from "../../src/reports/tedbir.js";

it("renders the required Turkish Madde 12 sections and period totals", async () => {
  const clock = { now: () => new Date("2026-08-09T12:30:00.000Z") };
  const store = new MemoryAuditStore();
  const writer = new AuditWriter(
    store,
    new Uint8Array(32).fill(9),
    new MemoryAuditCheckpointStore(),
    clock,
  );
  await writer.append({
    kind: "MASK_APPLIED",
    actor: "system:gateway",
    session_id: "session-1",
    request_sha256: sha256("request"),
    entities: [
      { type: "TR_TCKN", action: "mask", count: 2 },
      { type: "PERSON", action: "mask", count: 1 },
    ],
  });
  await writer.append({
    kind: "POLICY_CHANGED",
    actor: "user:admin",
    session_id: null,
    request_sha256: sha256("policy"),
    entities: [],
  });
  const data = await buildTedbirReportData(
    await store.list(),
    "2026-08-01",
    "2026-08-31",
    "2026-08-09T12:30:00.000Z",
    (records, from, to) => writer.verify(records, from, to),
  );
  expect(data.totals).toMatchObject({ events: 2, masked: 3, policyChanges: 1 });
  expect(data.chain).toMatchObject({ ok: true, verified: 2 });

  const pdf = await renderTedbirPdf(data);
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
  const parser = new PDFParse({ data: new Uint8Array(pdf) });
  try {
    const result = await parser.getText();
    const text = result.text.replace(/\s+/gu, " ").replace(/\/\s+/gu, "/");
    expect(text).toContain("KVKK Madde 12 Teknik Tedbir Raporu");
    expect(text).toContain("Veri Maskeleme");
    expect(text).toContain("Şifreleme/Anahtar Yönetimi");
    expect(text).toContain("Log Kayıtları");
    expect(text).toContain("Yetki Matrisi");
    expect(text).toContain("Denetim Kaydı Doğrulaması");
    expect(text).toContain("3 maskelenen alan");
  } finally {
    await parser.destroy();
  }
});
