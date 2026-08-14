import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { Pool, type QueryResultRow } from "pg";

export interface SqlResult<Row> {
  rows: Row[];
  rowCount?: number | null;
}

export interface SqlExecutor {
  query<Row extends QueryResultRow = QueryResultRow>(
    text: string,
    values?: readonly unknown[],
  ): Promise<SqlResult<Row>>;
  executeScript?(text: string): Promise<void>;
  transaction?<T>(operation: (executor: SqlExecutor) => Promise<T>): Promise<T>;
}

export class PostgresExecutor implements SqlExecutor {
  readonly #pool: Pool;

  constructor(connectionString: string) {
    this.#pool = new Pool({ connectionString });
  }

  async query<Row extends QueryResultRow = QueryResultRow>(
    text: string,
    values: readonly unknown[] = [],
  ): Promise<SqlResult<Row>> {
    return this.#pool.query<Row>(text, [...values]);
  }

  async close(): Promise<void> {
    await this.#pool.end();
  }

  async executeScript(text: string): Promise<void> {
    await this.#pool.query(text);
  }

  async transaction<T>(operation: (executor: SqlExecutor) => Promise<T>): Promise<T> {
    const client = await this.#pool.connect();
    try {
      await client.query("BEGIN");
      const executor: SqlExecutor = {
        query: (text, values = []) => client.query(text, [...values]),
      };
      const result = await operation(executor);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
}

export async function applyInitialMigration(executor: SqlExecutor): Promise<void> {
  await executeScript(executor, await loadMigration("0000_initial.sql"));
}

export async function applyMigrations(executor: SqlExecutor): Promise<void> {
  const initial = await loadMigration("0000_initial.sql");
  const securityHardening = await loadMigration("0001_security_hardening.sql");
  const migrate = async (transaction: SqlExecutor, lock: boolean): Promise<void> => {
    if (lock) await transaction.query("SELECT pg_advisory_xact_lock($1)", [1_214_839_720]);
    await transaction.query(
      `CREATE TABLE IF NOT EXISTS hushmark_schema_migrations (
         version text PRIMARY KEY,
         applied_at timestamptz NOT NULL DEFAULT now()
       )`,
    );
    const schema = await transaction.query<{ name: string | null }>(
      "SELECT to_regclass('public.roles')::text AS name",
    );
    if (schema.rows[0]?.name === null || schema.rows[0]?.name === undefined) {
      await executeScript(transaction, initial);
      await transaction.query(
        "INSERT INTO hushmark_schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
        ["0000_initial"],
      );
    }
    const applied = await transaction.query<{ version: string }>(
      "SELECT version FROM hushmark_schema_migrations WHERE version = $1",
      ["0001_security_hardening"],
    );
    if (applied.rows.length === 0) {
      await executeScript(transaction, securityHardening);
      await transaction.query("INSERT INTO hushmark_schema_migrations (version) VALUES ($1)", [
        "0001_security_hardening",
      ]);
    }
  };
  if (executor.transaction === undefined) await migrate(executor, false);
  else await executor.transaction((transaction) => migrate(transaction, true));
}

async function executeScript(executor: SqlExecutor, script: string): Promise<void> {
  if (executor.executeScript === undefined) await executor.query(script);
  else await executor.executeScript(script);
}

async function loadMigration(filename: string): Promise<string> {
  const candidates = [
    new URL(`../drizzle/${filename}`, import.meta.url),
    new URL(`../../drizzle/${filename}`, import.meta.url),
  ];
  for (const candidate of candidates) {
    try {
      return await readFile(fileURLToPath(candidate), "utf8");
    } catch (error) {
      if (!isMissingFile(error)) throw error;
    }
  }
  throw new Error(`gateway-enterprise migration ${filename} was not packaged`);
}

function isMissingFile(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    (error as Error & { code?: string }).code === "ENOENT"
  );
}
