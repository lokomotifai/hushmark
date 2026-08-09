"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { PageHead } from "@/components/page-head";
import { adminJson, type ProviderRecord } from "@/lib/admin";

export function Providers() {
  const t = useTranslations("Providers");
  const common = useTranslations("Common");
  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [pending, setPending] = useState(false);
  const [created, setCreated] = useState(false);

  const load = useCallback(async () => {
    setProviders(await adminJson<ProviderRecord[]>("providers"));
  }, []);
  useEffect(() => void load(), [load]);

  async function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setCreated(false);
    const form = new FormData(event.currentTarget);
    try {
      await adminJson<ProviderRecord>("providers", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          kind: form.get("kind"),
          base_url: form.get("base_url"),
          auth: form.get("auth"),
        }),
      });
      event.currentTarget.reset();
      await load();
      setCreated(true);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      <form className="card" onSubmit={(event) => void submit(event)}>
        <div className="form-grid">
          <label>
            {t("name")}
            <input name="name" required />
          </label>
          <label>
            {t("kind")}
            <select name="kind">
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </label>
          <label>
            {t("baseUrl")}
            <input name="base_url" required type="url" />
          </label>
          <label>
            {t("auth")}
            <input defaultValue="passthrough" name="auth" required />
          </label>
        </div>
        <div className="form-actions">
          <button className="button" disabled={pending} type="submit">
            {pending ? common("saving") : common("create")}
          </button>
          {created ? <span className="success-notice">{t("created")}</span> : null}
        </div>
      </form>
      <section className="card table-wrap">
        {providers.length === 0 ? <p className="notice">{common("empty")}</p> : null}
        {providers.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>{t("name")}</th>
                <th>{t("kind")}</th>
                <th>{t("baseUrl")}</th>
                <th>{t("auth")}</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((provider) => (
                <tr key={provider.id}>
                  <td>{provider.name}</td>
                  <td>
                    <span className="pill">{provider.kind}</span>
                  </td>
                  <td>{provider.baseUrl}</td>
                  <td className="matrix-code">{provider.auth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </>
  );
}
