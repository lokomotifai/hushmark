"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

export function LogoutButton() {
  const t = useTranslations("Common");
  const [pending, setPending] = useState(false);
  return (
    <button
      className="logout-button"
      disabled={pending}
      type="button"
      onClick={() => {
        setPending(true);
        void fetch("/api/admin/auth/logout", { method: "POST" }).finally(() => {
          window.location.assign("/login");
        });
      }}
    >
      {t("logout")}
    </button>
  );
}
