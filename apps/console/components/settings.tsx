"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState, type SyntheticEvent } from "react";

import { PageHead } from "@/components/page-head";
import { adminJson, type LicenseStatus } from "@/lib/admin";

export function Settings() {
  const t = useTranslations("Settings");
  const common = useTranslations("Common");
  const locale = useLocale();
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<"uploaded" | "error" | null>(null);

  const load = useCallback(async () => {
    setStatus(await adminJson<LicenseStatus>("license"));
  }, []);
  useEffect(() => void load(), [load]);

  async function upload(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage(null);
    const input = event.currentTarget.elements.namedItem("license-file");
    try {
      if (!(input instanceof HTMLInputElement) || input.files?.[0] === undefined) {
        throw new Error("missing license file");
      }
      const document = JSON.parse(await input.files[0].text()) as unknown;
      await adminJson<{ state: string }>("license", {
        method: "PUT",
        body: JSON.stringify(document),
      });
      await load();
      setMessage("uploaded");
    } catch {
      setMessage("error");
    } finally {
      setPending(false);
    }
  }

  async function changeLocale(nextLocale: "tr" | "en") {
    await fetch("/api/locale", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ locale: nextLocale }),
    });
    window.location.reload();
  }

  return (
    <>
      <PageHead eyebrow={t("eyebrow")} subtitle={t("subtitle")} title={t("title")} />
      <section className="card">
        <h2>{t("license")}</h2>
        {status === null ? <p className="notice">{common("loading")}</p> : null}
        {status !== null ? (
          <>
            <div className="license-banner" data-state={status.state}>
              {t(status.state)}
            </div>
            {status.license === null ? null : (
              <dl className="form-grid">
                <div>
                  <dt>{t("licensee")}</dt>
                  <dd>{status.license.licensee}</dd>
                </div>
                <div>
                  <dt>{t("tier")}</dt>
                  <dd>{status.license.tier}</dd>
                </div>
                <div>
                  <dt>{t("expires")}</dt>
                  <dd>
                    {new Intl.DateTimeFormat(locale).format(new Date(status.license.expires_at))}
                  </dd>
                </div>
              </dl>
            )}
          </>
        ) : null}
        <form onSubmit={(event) => void upload(event)}>
          <label>
            {t("upload")}
            <input accept="application/json,.json" name="license-file" required type="file" />
          </label>
          <div className="form-actions">
            <button className="button" disabled={pending} type="submit">
              {pending ? common("saving") : t("uploadButton")}
            </button>
            {message === "uploaded" ? (
              <span className="success-notice">{t("uploaded")}</span>
            ) : null}
            {message === "error" ? <span className="error-notice">{common("error")}</span> : null}
          </div>
        </form>
      </section>
      <section className="card">
        <h2>{t("language")}</h2>
        <div className="form-actions">
          <button
            className={locale === "tr" ? "button" : "secondary-button"}
            type="button"
            onClick={() => void changeLocale("tr")}
          >
            {t("turkish")}
          </button>
          <button
            className={locale === "en" ? "button" : "secondary-button"}
            type="button"
            onClick={() => void changeLocale("en")}
          >
            {t("english")}
          </button>
        </div>
      </section>
    </>
  );
}
