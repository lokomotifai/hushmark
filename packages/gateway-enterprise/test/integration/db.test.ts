import { PGlite } from "@electric-sql/pglite";
import type { QueryResultRow } from "pg";
import { afterEach, expect, it } from "vitest";

import { applyInitialMigration, type SqlExecutor, type SqlResult } from "../../src/db/client.js";
import { SqlPolicyRepository } from "../../src/policy/db.js";
import { testPolicy } from "../helpers.js";

let database: PGlite | undefined;
afterEach(async () => database?.close());

it("applies the PostgreSQL migration and persists an enterprise policy", async () => {
  database = new PGlite();
  await database.waitReady;
  await applyInitialMigration(new PgliteExecutor(database));
  const tables = await database.query<{ table_name: string }>(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name",
  );
  expect(tables.rows.map((row) => row.table_name)).toEqual([
    "api_keys",
    "audit_events",
    "policies",
    "providers",
    "roles",
    "users",
    "vault_records",
  ]);

  const repository = new SqlPolicyRepository(new PgliteExecutor(database));
  await repository.upsert({
    id: "30000000-0000-4000-8000-000000000001",
    name: "database-policy",
    priority: 50,
    match: { roles: ["operator"] },
    document: testPolicy(),
  });
  expect(await repository.list()).toMatchObject([
    { name: "database-policy", priority: 50, match: { roles: ["operator"] } },
  ]);
});

class PgliteExecutor implements SqlExecutor {
  constructor(private readonly database: PGlite) {}

  async query<Row extends QueryResultRow = QueryResultRow>(
    text: string,
    values: readonly unknown[] = [],
  ): Promise<SqlResult<Row>> {
    const result = await this.database.query<Row>(text, [...values]);
    return {
      rows: result.rows,
      ...(result.affectedRows === undefined ? {} : { rowCount: result.affectedRows }),
    };
  }

  async executeScript(text: string): Promise<void> {
    await this.database.exec(text);
  }
}
