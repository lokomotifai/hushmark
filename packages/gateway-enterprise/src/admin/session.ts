import { randomBytes } from "node:crypto";

import type { AdminRole } from "./rbac.js";

export interface AdminPrincipal {
  userId: string;
  role: AdminRole;
}

interface SessionRecord extends AdminPrincipal {
  expiresAt: number;
}

export class AdminSessions {
  readonly #sessions = new Map<string, SessionRecord>();

  constructor(
    private readonly ttlMs = 8 * 60 * 60 * 1_000,
    private readonly now: () => number = Date.now,
  ) {}

  create(principal: AdminPrincipal): string {
    const token = randomBytes(32).toString("base64url");
    this.#sessions.set(token, { ...principal, expiresAt: this.now() + this.ttlMs });
    return token;
  }

  resolve(token: string): AdminPrincipal | null {
    const record = this.#sessions.get(token);
    if (record === undefined || record.expiresAt <= this.now()) {
      this.#sessions.delete(token);
      return null;
    }
    return { userId: record.userId, role: record.role };
  }

  revoke(token: string): void {
    this.#sessions.delete(token);
  }
}
