"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { PageHead } from "@/components/page-head";
import { adminDownload, adminJson, type AuditPage } from "@/lib/admin";

interface VerifyResult {
  ok: boolean;
  firstBrokenSeq: number | null;
  verified: number;
}

export function AuditLog() {
  const t = useTranslations("Audit");
  const common = useTranslations("Common");
  const locale = useLocale();
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<AuditPage | null>(null);
  const [verification, setVerification] = useState<VerifyResult | null>(null);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    setResult(await adminJson<AuditPage>(`audit/events?page=${String(page)}&limit=20`));
  }, [page]);
  useEffect(() => void load(), [load]);

  async function verify() {
    setPending(true);
    try {
      setVerification(await adminJson<VerifyResult>("audit/verify?from=1&to=latest"));
    } finally {
      setPending(false);
    }
  }

  async function exportAudit() {
    setPending(true);
    try {
      await adminDownload("audit/export?from=1&to=latest", "hushmark-audit.ndjson");
    } finally {
      setPending(false);
    }
  }

  const pages = Math.max(1, Math.ceil((result?.total ?? 0) / 20));
  return (
    <>
      <PageHead
        action={
          <button className="button" disabled={pending} type="button" onClick={() => void verify()}>
            {t("verify")}
          </button>
        }
        eyebrow={t("eyebrow")}
        subtitle={t("subtitle")}
        title={t("title")}
      />
      <section className="card">
        <div className="toolbar">
          <div>
            {verification?.ok === true ? (
              <span className="success-notice">
                {t("verified", { count: verification.verified })}
              </span>
            ) : null}
            {verification?.ok === false ? (
              <span className="error-notice">
                {t("broken", { seq: verification.firstBrokenSeq ?? 0 })}
              </span>
            ) : null}
          </div>
          <button
            className="secondary-button"
            disabled={pending}
            type="button"
            onClick={() => void exportAudit()}
          >
            {t("export")}
          </button>
        </div>
        <div className="table-wrap">
          {result === null ? <p className="notice">{common("loading")}</p> : null}
          {result?.events.length === 0 ? <p className="notice">{common("empty")}</p> : null}
          {result !== null && result.events.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>{t("sequence")}</th>
                  <th>{t("time")}</th>
                  <th>{t("event")}</th>
                  <th>{t("actor")}</th>
                  <th>{t("entities")}</th>
                </tr>
              </thead>
              <tbody>
                {result.events.map((event) => (
                  <tr key={event.seq}>
                    <td>{event.seq}</td>
                    <td>
                      {new Intl.DateTimeFormat(locale, {
                        dateStyle: "short",
                        timeStyle: "short",
                      }).format(new Date(event.ts))}
                    </td>
                    <td>
                      <span className="pill">{event.kind}</span>
                    </td>
                    <td>{event.actor}</td>
                    <td>
                      {event.entities.length === 0
                        ? "—"
                        : event.entities
                            .map((entity) => `${entity.type} × ${String(entity.count)}`)
                            .join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
        <div className="pagination">
          <button
            className="secondary-button"
            disabled={page <= 1}
            type="button"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            {t("previous")}
          </button>
          <span>{t("page", { page, pages })}</span>
          <button
            className="secondary-button"
            disabled={page >= pages}
            type="button"
            onClick={() => setPage((current) => Math.min(pages, current + 1))}
          >
            {t("next")}
          </button>
        </div>
      </section>
    </>
  );
}
