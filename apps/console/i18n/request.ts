import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import en from "../messages/en.json";
import tr from "../messages/tr.json";

export const locales = ["tr", "en"] as const;
export type Locale = (typeof locales)[number];

export default getRequestConfig(async () => {
  const store = await cookies();
  const requested = store.get("hm_locale")?.value;
  const locale: Locale = requested === "en" ? "en" : "tr";
  return {
    locale,
    messages: locale === "en" ? en : tr,
  };
});
