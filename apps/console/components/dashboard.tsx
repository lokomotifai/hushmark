"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { PageHead } from "@/components/page-head";
import { adminJson, type MetricsSummary } from "@/lib/admin";

export function Dashboard() {
  const t = useTranslations("Dashboard");
  const common = useTranslations("Common");
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    void adminJson<MetricsSummary>("metrics/summary")
      .then(setMetrics)
      .catch(() => setError(true));
  }, []);

  const entries = Object.entries(metrics?.entity_counts ?? {}).sort(
    (left, right) => right[1] - left[1],
  );
  const max = Math.max(1, ...entries.map(([, count]) => count));
  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      {error ? <div className="error-notice">{common("error")}</div> : null}
      <div className="metric-grid">
        <section className="card metric-card">
          <span className="metric-value">{metrics?.masked ?? "—"}</span>
          <span className="metric-label">{t("masked")}</span>
        </section>
        <section className="card metric-card">
          <span className="metric-value">{metrics?.blocked ?? "—"}</span>
          <span className="metric-label">{t("blocked")}</span>
        </section>
      </div>
      <div className="split-grid">
        <section className="card">
          <h2>{t("types")}</h2>
          {metrics === null ? <p className="notice">{common("loading")}</p> : null}
          {metrics !== null && entries.length === 0 ? (
            <p className="notice">{common("empty")}</p>
          ) : null}
          <div className="bar-list">
            {entries.map(([type, count]) => (
              <div className="bar-row" key={type}>
                <span className="matrix-code">{type}</span>
                <span className="bar-track">
                  <span
                    className="bar-fill"
                    style={{ width: `${String(Math.max(4, (count / max) * 100))}%` }}
                  />
                </span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </section>
        <aside className="card status-panel">
          <h2>
            <span className="status-dot" />
            {t("protected")}
          </h2>
          <p>{t("protectedBody")}</p>
        </aside>
      </div>
    </>
  );
}
