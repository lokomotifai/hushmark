"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { PageHead } from "@/components/page-head";
import { adminJson, type ApiKeySummary } from "@/lib/admin";

export function ApiKeys() {
  const t = useTranslations("ApiKeys");
  const common = useTranslations("Common");
  const locale = useLocale();
  const [keys, setKeys] = useState<ApiKeySummary[]>([]);
  const [secret, setSecret] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [revoked, setRevoked] = useState(false);

  const load = useCallback(async () => {
    setKeys(await adminJson<ApiKeySummary[]>("api-keys"));
  }, []);
  useEffect(() => void load(), [load]);

  async function create(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setSecret(null);
    const form = new FormData(event.currentTarget);
    try {
      const issued = await adminJson<ApiKeySummary & { secret: string }>("api-keys", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name") }),
      });
      setSecret(issued.secret);
      event.currentTarget.reset();
      await load();
    } finally {
      setPending(false);
    }
  }

  async function revoke(id: string) {
    setRevoked(false);
    await adminJson<{ status: string }>(`api-keys/${id}`, { method: "DELETE" });
    await load();
    setRevoked(true);
  }

  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      <form className="card" onSubmit={(event) => void create(event)}>
        <div className="form-grid">
          <label className="wide">
            {t("name")}
            <input name="name" required />
          </label>
        </div>
        <div className="form-actions">
          <button className="button" disabled={pending} type="submit">
            {pending ? common("saving") : common("create")}
          </button>
          {revoked ? <span className="success-notice">{t("revoked")}</span> : null}
        </div>
        {secret === null ? null : (
          <div className="secret-panel" role="status">
            <strong>{t("revealTitle")}</strong>
            <p>{t("revealBody")}</p>
            <code className="secret-value">{secret}</code>
          </div>
        )}
      </form>
      <section className="card table-wrap">
        {keys.length === 0 ? <p className="notice">{common("empty")}</p> : null}
        {keys.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>{t("name")}</th>
                <th>{t("prefix")}</th>
                <th>{t("createdAt")}</th>
                <th>{common("status")}</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td className="matrix-code">{key.prefix}</td>
                  <td>{new Intl.DateTimeFormat(locale).format(new Date(key.createdAt))}</td>
                  <td>
                    {key.revokedAt === null ? (
                      <button
                        className="danger-button"
                        type="button"
                        onClick={() => void revoke(key.id)}
                      >
                        {common("revoke")}
                      </button>
                    ) : (
                      <span className="pill">{t("revoked")}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </>
  );
}
