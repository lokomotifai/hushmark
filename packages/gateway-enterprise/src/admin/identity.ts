import { randomBytes, randomUUID } from "node:crypto";

import argon2 from "argon2";
import { z } from "zod";

import type { SqlExecutor } from "../db/client.js";
import { AdminRoleSchema, type AdminRole } from "./rbac.js";

export interface AdminUser {
  id: string;
  email: string;
  passwordHash: string;
  role: AdminRole;
  enabled: boolean;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  revokedAt: string | null;
  createdAt: string;
}

export interface ProviderRecord {
  id: string;
  name: string;
  kind: "openai" | "anthropic";
  baseUrl: string;
  auth: string;
}

export interface IdentityRepository {
  findUserByEmail(email: string): Promise<AdminUser | null>;
  putUser(user: AdminUser): Promise<void>;
  listApiKeys(): Promise<ApiKeySummary[]>;
  putApiKey(summary: ApiKeySummary, secretHash: string): Promise<void>;
  revokeApiKey(id: string, at: string): Promise<boolean>;
  authenticateApiKey(secret: string): Promise<string | null>;
  listProviders(): Promise<ProviderRecord[]>;
  putProvider(provider: ProviderRecord): Promise<void>;
}

export class MemoryIdentityRepository implements IdentityRepository {
  readonly #users = new Map<string, AdminUser>();
  readonly #apiKeys = new Map<string, ApiKeySummary & { secretHash: string }>();
  readonly #providers = new Map<string, ProviderRecord>();

  findUserByEmail(email: string): Promise<AdminUser | null> {
    const user = this.#users.get(normalizeEmail(email));
    return Promise.resolve(user === undefined ? null : structuredClone(user));
  }

  putUser(user: AdminUser): Promise<void> {
    this.#users.set(normalizeEmail(user.email), structuredClone(user));
    return Promise.resolve();
  }

  listApiKeys(): Promise<ApiKeySummary[]> {
    return Promise.resolve(
      [...this.#apiKeys.values()].map((record) => ({
        id: record.id,
        name: record.name,
        prefix: record.prefix,
        revokedAt: record.revokedAt,
        createdAt: record.createdAt,
      })),
    );
  }

  putApiKey(summary: ApiKeySummary, secretHash: string): Promise<void> {
    this.#apiKeys.set(summary.id, { ...structuredClone(summary), secretHash });
    return Promise.resolve();
  }

  revokeApiKey(id: string, at: string): Promise<boolean> {
    const record = this.#apiKeys.get(id);
    if (record === undefined) return Promise.resolve(false);
    record.revokedAt = at;
    return Promise.resolve(true);
  }

  async authenticateApiKey(secret: string): Promise<string | null> {
    let checkedCandidate = false;
    for (const record of this.#apiKeys.values()) {
      if (record.revokedAt !== null || record.prefix !== secret.slice(0, 18)) continue;
      checkedCandidate = true;
      if (await verifySecret(record.secretHash, secret)) return record.id;
    }
    if (!checkedCandidate) await verifySecret(await DUMMY_API_KEY_HASH, secret);
    return null;
  }

  listProviders(): Promise<ProviderRecord[]> {
    return Promise.resolve([...this.#providers.values()].map((value) => structuredClone(value)));
  }

  putProvider(provider: ProviderRecord): Promise<void> {
    this.#providers.set(provider.id, structuredClone(provider));
    return Promise.resolve();
  }
}

export class SqlIdentityRepository implements IdentityRepository {
  constructor(private readonly sql: SqlExecutor) {}

  async findUserByEmail(email: string): Promise<AdminUser | null> {
    const result = await this.sql.query<{
      id: string;
      email: string;
      password_hash: string;
      role: string;
      enabled: boolean;
    }>("SELECT id, email, password_hash, role, enabled FROM users WHERE email = $1 LIMIT 1", [
      normalizeEmail(email),
    ]);
    const row = result.rows[0];
    return row === undefined
      ? null
      : {
          id: row.id,
          email: row.email,
          passwordHash: row.password_hash,
          role: AdminRoleSchema.parse(row.role),
          enabled: row.enabled,
        };
  }

  async putUser(user: AdminUser): Promise<void> {
    await this.sql.query(
      `INSERT INTO users (id, email, password_hash, role, enabled)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email,
       password_hash = EXCLUDED.password_hash, role = EXCLUDED.role, enabled = EXCLUDED.enabled`,
      [user.id, normalizeEmail(user.email), user.passwordHash, user.role, user.enabled],
    );
  }

  async listApiKeys(): Promise<ApiKeySummary[]> {
    const result = await this.sql.query<{
      id: string;
      name: string;
      prefix: string;
      revoked_at: Date | string | null;
      created_at: Date | string;
    }>("SELECT id, name, prefix, revoked_at, created_at FROM api_keys ORDER BY created_at ASC");
    return result.rows.map((row) => ({
      id: row.id,
      name: row.name,
      prefix: row.prefix,
      revokedAt: row.revoked_at instanceof Date ? row.revoked_at.toISOString() : row.revoked_at,
      createdAt: row.created_at instanceof Date ? row.created_at.toISOString() : row.created_at,
    }));
  }

  async putApiKey(summary: ApiKeySummary, secretHash: string): Promise<void> {
    await this.sql.query(
      `INSERT INTO api_keys (id, name, prefix, secret_hash, revoked_at, created_at)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [summary.id, summary.name, summary.prefix, secretHash, summary.revokedAt, summary.createdAt],
    );
  }

  async revokeApiKey(id: string, at: string): Promise<boolean> {
    const result = await this.sql.query(
      "UPDATE api_keys SET revoked_at = $2 WHERE id = $1 AND revoked_at IS NULL",
      [id, at],
    );
    return (result.rowCount ?? 0) > 0;
  }

  async authenticateApiKey(secret: string): Promise<string | null> {
    const result = await this.sql.query<{ id: string; secret_hash: string }>(
      `SELECT id, secret_hash FROM api_keys
       WHERE prefix = $1 AND revoked_at IS NULL LIMIT 1`,
      [secret.slice(0, 18)],
    );
    const record = result.rows[0];
    if (record === undefined) {
      await verifySecret(await DUMMY_API_KEY_HASH, secret);
      return null;
    }
    return (await verifySecret(record.secret_hash, secret)) ? record.id : null;
  }

  async listProviders(): Promise<ProviderRecord[]> {
    const result = await this.sql.query<{
      id: string;
      name: string;
      kind: "openai" | "anthropic";
      base_url: string;
      auth: string;
    }>("SELECT id, name, kind, base_url, auth FROM providers ORDER BY name ASC");
    return result.rows.map((row) => ({
      id: row.id,
      name: row.name,
      kind: row.kind,
      baseUrl: row.base_url,
      auth: row.auth,
    }));
  }

  async putProvider(provider: ProviderRecord): Promise<void> {
    await this.sql.query(
      `INSERT INTO providers (id, name, kind, base_url, auth) VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, kind = EXCLUDED.kind,
       base_url = EXCLUDED.base_url, auth = EXCLUDED.auth`,
      [provider.id, provider.name, provider.kind, provider.baseUrl, provider.auth],
    );
  }
}

export async function hashSecret(secret: string): Promise<string> {
  return argon2.hash(secret, { type: argon2.argon2id });
}

export function verifySecret(hash: string, secret: string): Promise<boolean> {
  return argon2.verify(hash, secret);
}

export async function issueApiKey(
  name: string,
  now = new Date(),
): Promise<{
  secret: string;
  summary: ApiKeySummary;
  secretHash: string;
}> {
  const validatedName = z.string().min(1).max(120).parse(name);
  const secret = `hm_k1_${randomBytes(32).toString("base64url")}`;
  return {
    secret,
    summary: {
      id: randomUUID(),
      name: validatedName,
      prefix: secret.slice(0, 18),
      revokedAt: null,
      createdAt: now.toISOString(),
    },
    secretHash: await hashSecret(secret),
  };
}

function normalizeEmail(email: string): string {
  return z.email().parse(email).normalize("NFC").toLowerCase();
}

const DUMMY_API_KEY_HASH = hashSecret("hushmark-dummy-api-key-for-constant-work");
