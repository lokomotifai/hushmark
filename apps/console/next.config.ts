import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const scriptSource =
  process.env.NODE_ENV === "development"
    ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
    : "script-src 'self' 'unsafe-inline'";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  headers() {
    return Promise.resolve([
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: `default-src 'self'; base-uri 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; object-src 'none'; ${scriptSource}; style-src 'self' 'unsafe-inline'`,
          },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ]);
  },
};

export default createNextIntlPlugin()(nextConfig);
