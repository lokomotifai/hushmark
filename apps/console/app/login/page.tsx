import { getTranslations } from "next-intl/server";

import { LoginForm } from "@/components/login-form";

export default async function LoginPage() {
  const t = await getTranslations("Login");
  return (
    <main className="login-page">
      <section className="login-card">
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1>{t("title")}</h1>
        <p className="subtitle">{t("subtitle")}</p>
        <LoginForm />
      </section>
    </main>
  );
}
