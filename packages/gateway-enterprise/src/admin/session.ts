import { createHash, randomBytes } from "node:crypto";

import type { AdminRole } from "./rbac.js";
import type { SqlExecutor } from "../db/client.js";

export interface AdminPrincipal {
  userId: string;
  role: AdminRole;
}

export interface AdminSessionStore {
  create(principal: AdminPrincipal): Promise<string>;
  resolve(token: string): Promise<AdminPrincipal | null>;
  revoke(token: string): Promise<void>;
}

interface SessionRecord extends AdminPrincipal {
  expiresAt: number;
}

export class AdminSessions implements AdminSessionStore {
  readonly #sessions = new Map<string, SessionRecord>();

  constructor(
    private readonly ttlMs = 8 * 60 * 60 * 1_000,
    private readonly now: () => number = Date.now,
  ) {}

  create(principal: AdminPrincipal): Promise<string> {
    const token = randomBytes(32).toString("base64url");
    this.#sessions.set(token, { ...principal, expiresAt: this.now() + this.ttlMs });
    return Promise.resolve(token);
  }

  resolve(token: string): Promise<AdminPrincipal | null> {
    const record = this.#sessions.get(token);
    if (record === undefined || record.expiresAt <= this.now()) {
      this.#sessions.delete(token);
      return Promise.resolve(null);
    }
    return Promise.resolve({ userId: record.userId, role: record.role });
  }

  revoke(token: string): Promise<void> {
    this.#sessions.delete(token);
    return Promise.resolve();
  }
}

export class SqlAdminSessions implements AdminSessionStore {
  constructor(
    private readonly sql: SqlExecutor,
    private readonly ttlMs = 8 * 60 * 60 * 1_000,
    private readonly now: () => number = Date.now,
  ) {}

  async create(principal: AdminPrincipal): Promise<string> {
    const token = randomBytes(32).toString("base64url");
    await this.sql.query(
      `INSERT INTO admin_sessions (token_hash, user_id, expires_at)
       VALUES ($1, $2, $3)`,
      [tokenHash(token), principal.userId, new Date(this.now() + this.ttlMs)],
    );
    return token;
  }

  async resolve(token: string): Promise<AdminPrincipal | null> {
    const result = await this.sql.query<{
      user_id: string;
      role: AdminRole;
      enabled: boolean;
      expires_at: Date | string;
    }>(
      `SELECT s.user_id, u.role, u.enabled, s.expires_at
       FROM admin_sessions s JOIN users u ON u.id = s.user_id
       WHERE s.token_hash = $1 LIMIT 1`,
      [tokenHash(token)],
    );
    const record = result.rows[0];
    const expiresAt =
      record?.expires_at instanceof Date
        ? record.expires_at.getTime()
        : new Date(record?.expires_at ?? 0).getTime();
    if (record === undefined || !record.enabled || expiresAt <= this.now()) {
      await this.revoke(token);
      return null;
    }
    return { userId: record.user_id, role: record.role };
  }

  async revoke(token: string): Promise<void> {
    await this.sql.query("DELETE FROM admin_sessions WHERE token_hash = $1", [tokenHash(token)]);
  }
}

function tokenHash(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
