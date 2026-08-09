import { defineConfig } from "drizzle-kit";

export default defineConfig({
  dialect: "postgresql",
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dbCredentials: {
    url: process.env.HUSHMARK_DATABASE_URL ?? "postgres://hushmark@127.0.0.1:5432/hushmark",
  },
});
