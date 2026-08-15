import { PGlite } from "@electric-sql/pglite";
import type { QueryResultRow } from "pg";
import { afterEach, expect, it } from "vitest";

import {
  applyInitialMigration,
  applyMigrations,
  type SqlExecutor,
  type SqlResult,
} from "../../src/db/client.js";
import { SqlPolicyRepository } from "../../src/policy/db.js";
import { testPolicy } from "../helpers.js";

const DATABASE_TEST_TIMEOUT_MS = 15_000;

let database: PGlite | undefined;
afterEach(async () => database?.close());

it(
  "applies the PostgreSQL migration and persists an enterprise policy",
  async () => {
    database = new PGlite();
    await database.waitReady;
    await applyInitialMigration(new PgliteExecutor(database));
    const tables = await database.query<{ table_name: string }>(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name",
    );
    expect(tables.rows.map((row) => row.table_name)).toEqual([
      "admin_sessions",
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
  },
  DATABASE_TEST_TIMEOUT_MS,
);

it(
  "migrates the pre-hardening schema and discards unscoped vault rows",
  async () => {
    database = new PGlite();
    await database.waitReady;
    await database.exec(`
    CREATE TABLE roles (name text PRIMARY KEY);
    INSERT INTO roles (name) VALUES ('admin'), ('operator'), ('auditor');
    CREATE TABLE users (
      id uuid PRIMARY KEY, email text NOT NULL UNIQUE, password_hash text NOT NULL,
      role text NOT NULL REFERENCES roles(name), enabled boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE audit_events (
      seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ts timestamptz NOT NULL,
      kind text NOT NULL, actor text NOT NULL, session_id text, request_sha256 text NOT NULL,
      entities jsonb NOT NULL DEFAULT '[]'::jsonb, prev_hash text NOT NULL, hash text NOT NULL
    );
    CREATE TABLE vault_records (
      session_id text NOT NULL, placeholder text NOT NULL, ciphertext bytea NOT NULL,
      iv bytea NOT NULL, tag bytea NOT NULL, wrapped_key text NOT NULL,
      entity_type text NOT NULL, expires_at timestamptz NOT NULL,
      PRIMARY KEY (session_id, placeholder)
    );
    INSERT INTO vault_records VALUES (
      'legacy-session', '[AD_1]', '\\x01', '\\x02', '\\x03', 'wrapped', 'PERSON', now()
    );
    `);

    const executor = new PgliteExecutor(database);
    await applyMigrations(executor);
    const vaultRows = await database.query<{ count: string }>(
      "SELECT COUNT(*)::text AS count FROM vault_records",
    );
    expect(vaultRows.rows[0]?.count).toBe("0");
    const columns = await database.query<{ column_name: string; is_nullable: string }>(
      `SELECT column_name, is_nullable FROM information_schema.columns
     WHERE table_name = 'vault_records' AND column_name IN ('tenant_id', 'value_hmac')
     ORDER BY column_name`,
    );
    expect(columns.rows).toEqual([
      { column_name: "tenant_id", is_nullable: "NO" },
      { column_name: "value_hmac", is_nullable: "NO" },
    ]);
    await executor.query(
      `INSERT INTO audit_events
     (seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash)
     VALUES ($1, now(), 'LOGIN_OK', 'user:test', NULL, $2, '[]'::jsonb, $2, $2)`,
      [1, "0".repeat(64)],
    );
    await applyMigrations(executor);
    const versions = await database.query<{ version: string }>(
      "SELECT version FROM hushmark_schema_migrations ORDER BY version",
    );
    expect(versions.rows.map((row) => row.version)).toEqual([
      "0001_security_hardening",
      "0002_vault_session_keys",
      "0003_vault_placeholder_counters",
    ]);
  },
  DATABASE_TEST_TIMEOUT_MS,
);

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
