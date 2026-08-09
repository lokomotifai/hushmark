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
}

export async function applyInitialMigration(executor: SqlExecutor): Promise<void> {
  const candidates = [
    new URL("../drizzle/0000_initial.sql", import.meta.url),
    new URL("../../drizzle/0000_initial.sql", import.meta.url),
  ];
  for (const candidate of candidates) {
    try {
      const migration = await readFile(fileURLToPath(candidate), "utf8");
      if (executor.executeScript === undefined) await executor.query(migration);
      else await executor.executeScript(migration);
      return;
    } catch (error) {
      if (!isMissingFile(error)) throw error;
    }
  }
  throw new Error("gateway-enterprise initial migration was not packaged");
}

function isMissingFile(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    (error as Error & { code?: string }).code === "ENOENT"
  );
}
