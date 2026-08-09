"use client";

import { useTranslations } from "next-intl";
import { useState, type SyntheticEvent } from "react";

export function LoginForm() {
  const t = useTranslations("Login");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(false);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/admin/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      if (!response.ok) {
        setError(true);
        return;
      }
      window.location.assign("/dashboard");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="login-form" onSubmit={(event) => void submit(event)}>
      <label>
        {t("email")}
        <input autoComplete="username" name="email" required type="email" />
      </label>
      <label>
        {t("password")}
        <input autoComplete="current-password" name="password" required type="password" />
      </label>
      {error ? <div className="error-notice">{t("invalid")}</div> : null}
      <button className="button" disabled={pending} type="submit">
        {pending ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
