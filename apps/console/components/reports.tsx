"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { PageHead } from "@/components/page-head";

function initialPeriod(): { from: string; to: string } {
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  const from = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1))
    .toISOString()
    .slice(0, 10);
  return { from, to };
}

export function Reports() {
  const t = useTranslations("Reports");
  const [period, setPeriod] = useState(initialPeriod);
  const href = `/api/admin/reports/tedbir?from=${encodeURIComponent(period.from)}&to=${encodeURIComponent(period.to)}&format=pdf`;
  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      <section className="card">
        <div className="form-grid">
          <label>
            {t("from")}
            <input
              name="report-from"
              type="date"
              value={period.from}
              onChange={(event) =>
                setPeriod((current) => ({ ...current, from: event.target.value }))
              }
            />
          </label>
          <label>
            {t("to")}
            <input
              name="report-to"
              type="date"
              value={period.to}
              onChange={(event) => setPeriod((current) => ({ ...current, to: event.target.value }))}
            />
          </label>
        </div>
        <div className="form-actions">
          <a className="button" download href={href}>
            {t("generate")}
          </a>
        </div>
      </section>
      <section className="card">
        <h2>{t("mappingTitle")}</h2>
        <div className="measure-list">
          <div className="measure-item">{t("masking")}</div>
          <div className="measure-item">{t("vault")}</div>
          <div className="measure-item">{t("logs")}</div>
          <div className="measure-item">{t("matrix")}</div>
        </div>
      </section>
    </>
  );
}
