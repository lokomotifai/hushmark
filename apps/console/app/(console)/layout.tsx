import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { LogoutButton } from "@/components/logout-button";

const nav = [
  ["dashboard", "/dashboard"],
  ["policies", "/policies"],
  ["providers", "/providers"],
  ["apiKeys", "/api-keys"],
  ["audit", "/audit"],
  ["reports", "/reports"],
  ["settings", "/settings"],
] as const;

export default async function ConsoleLayout({ children }: Readonly<{ children: ReactNode }>) {
  const t = await getTranslations("Nav");
  return (
    <div className="console-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">H</span>
          <span>
            <strong>Hushmark</strong>
            <small>{t("eyebrow")}</small>
          </span>
        </Link>
        <nav className="nav-list">
          {nav.map(([key, href]) => (
            <Link className="nav-link" href={href} key={key}>
              <span className="nav-glyph" />
              {t(key)}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <LogoutButton />
        </div>
      </aside>
      <main className="main-area">{children}</main>
    </div>
  );
}
