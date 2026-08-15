import type { EntityType } from "@hushmark/shared";
import type { VaultScope } from "@hushmark/gateway";

import type { SqlExecutor } from "../db/client.js";

export interface EncryptedVaultRecord {
  tenantId: string;
  sessionId: string;
  placeholder: string;
  ciphertext: Uint8Array;
  iv: Uint8Array;
  tag: Uint8Array;
  wrappedKey: string;
  entityType: EntityType;
  valueHmac: string;
  expiresAt: Date;
}

export interface VaultRepository {
  getSessionKey(scope: VaultScope): Promise<string | null>;
  claimSessionKey(scope: VaultScope, candidateWrappedKey: string): Promise<string>;
  allocatePlaceholder(
    scope: VaultScope,
    label: string,
    suffix: string,
    minimum: number,
  ): Promise<string>;
  put(record: EncryptedVaultRecord): Promise<void>;
  get(scope: VaultScope, placeholder: string): Promise<EncryptedVaultRecord | null>;
  getByValueHmac(
    scope: VaultScope,
    entityType: EntityType,
    valueHmac: string,
  ): Promise<EncryptedVaultRecord | null>;
  listSession(scope: VaultScope): Promise<EncryptedVaultRecord[]>;
  deleteExpired(now: Date): Promise<number>;
}

export class MemoryVaultRepository implements VaultRepository {
  readonly #records = new Map<string, EncryptedVaultRecord>();
  readonly #sessionKeys = new Map<string, string>();
  readonly #placeholderCounters = new Map<string, number>();

  getSessionKey(scope: VaultScope): Promise<string | null> {
    return Promise.resolve(this.#sessionKeys.get(sessionKey(scope)) ?? null);
  }

  claimSessionKey(scope: VaultScope, candidateWrappedKey: string): Promise<string> {
    const session = sessionKey(scope);
    const existing = this.#sessionKeys.get(session);
    if (existing !== undefined) return Promise.resolve(existing);
    this.#sessionKeys.set(session, candidateWrappedKey);
    return Promise.resolve(candidateWrappedKey);
  }

  allocatePlaceholder(
    scope: VaultScope,
    label: string,
    suffix: string,
    minimum: number,
  ): Promise<string> {
    const counterKey = `${sessionKey(scope)}\0${label}\0${suffix}`;
    let current = this.#placeholderCounters.get(counterKey);
    if (current === undefined) {
      current = 0;
      const pattern = new RegExp(`^\\[${label}_([1-9][0-9]{0,4})\\]${suffix}$`, "u");
      for (const record of this.#records.values()) {
        if (record.tenantId !== scope.tenantId || record.sessionId !== scope.sessionId) continue;
        const match = pattern.exec(record.placeholder);
        if (match?.[1] !== undefined) current = Math.max(current, Number(match[1]));
      }
    }
    const next = Math.max(current + 1, minimum);
    if (next > 99_999) throw new Error("vault placeholder space exhausted");
    this.#placeholderCounters.set(counterKey, next);
    return Promise.resolve(`[${label}_${String(next)}]${suffix}`);
  }

  put(record: EncryptedVaultRecord): Promise<void> {
    this.#records.set(key(record, record.placeholder), cloneRecord(record));
    return Promise.resolve();
  }

  get(scope: VaultScope, placeholder: string): Promise<EncryptedVaultRecord | null> {
    const record = this.#records.get(key(scope, placeholder));
    return Promise.resolve(record === undefined ? null : cloneRecord(record));
  }

  getByValueHmac(
    scope: VaultScope,
    entityType: EntityType,
    valueHmac: string,
  ): Promise<EncryptedVaultRecord | null> {
    const record = [...this.#records.values()].find(
      (candidate) =>
        candidate.tenantId === scope.tenantId &&
        candidate.sessionId === scope.sessionId &&
        candidate.entityType === entityType &&
        candidate.valueHmac === valueHmac,
    );
    return Promise.resolve(record === undefined ? null : cloneRecord(record));
  }

  listSession(scope: VaultScope): Promise<EncryptedVaultRecord[]> {
    return Promise.resolve(
      [...this.#records.values()]
        .filter(
          (record) => record.tenantId === scope.tenantId && record.sessionId === scope.sessionId,
        )
        .map(cloneRecord),
    );
  }

  deleteExpired(now: Date): Promise<number> {
    let count = 0;
    for (const [recordKey, record] of this.#records) {
      if (record.expiresAt <= now) {
        this.#records.delete(recordKey);
        count += 1;
      }
    }
    return Promise.resolve(count);
  }
}

export class SqlVaultRepository implements VaultRepository {
  constructor(private readonly sql: SqlExecutor) {}

  async getSessionKey(scope: VaultScope): Promise<string | null> {
    const result = await this.sql.query<{ wrapped_key: string }>(
      `SELECT wrapped_key FROM vault_session_keys
       WHERE tenant_id = $1 AND session_id = $2`,
      [scope.tenantId, scope.sessionId],
    );
    return result.rows[0]?.wrapped_key ?? null;
  }

  async claimSessionKey(scope: VaultScope, candidateWrappedKey: string): Promise<string> {
    await this.sql.query(
      `INSERT INTO vault_session_keys (tenant_id, session_id, wrapped_key)
       VALUES ($1, $2, $3) ON CONFLICT (tenant_id, session_id) DO NOTHING`,
      [scope.tenantId, scope.sessionId, candidateWrappedKey],
    );
    const result = await this.sql.query<{ wrapped_key: string }>(
      `SELECT wrapped_key FROM vault_session_keys
       WHERE tenant_id = $1 AND session_id = $2`,
      [scope.tenantId, scope.sessionId],
    );
    const wrapped = result.rows[0]?.wrapped_key;
    if (wrapped === undefined) throw new Error("vault session key claim failed");
    return wrapped;
  }

  async allocatePlaceholder(
    scope: VaultScope,
    label: string,
    suffix: string,
    minimum: number,
  ): Promise<string> {
    const result = await this.sql.query<{ next_value: string | number }>(
      `INSERT INTO vault_placeholder_counters
       (tenant_id, session_id, label, suffix, next_value)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (tenant_id, session_id, label, suffix) DO UPDATE
       SET next_value = GREATEST(vault_placeholder_counters.next_value + 1, EXCLUDED.next_value)
       RETURNING next_value`,
      [scope.tenantId, scope.sessionId, label, suffix, minimum],
    );
    const next = Number(result.rows[0]?.next_value);
    if (!Number.isInteger(next) || next < 1 || next > 99_999) {
      throw new Error("vault placeholder space exhausted");
    }
    return `[${label}_${String(next)}]${suffix}`;
  }

  async put(record: EncryptedVaultRecord): Promise<void> {
    await this.sql.query(
      `INSERT INTO vault_records
       (tenant_id, session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type,
        value_hmac, expires_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       ON CONFLICT (tenant_id, session_id, placeholder) DO UPDATE SET ciphertext = EXCLUDED.ciphertext,
       iv = EXCLUDED.iv, tag = EXCLUDED.tag, wrapped_key = EXCLUDED.wrapped_key,
       entity_type = EXCLUDED.entity_type, value_hmac = EXCLUDED.value_hmac,
       expires_at = EXCLUDED.expires_at`,
      [
        record.tenantId,
        record.sessionId,
        record.placeholder,
        Buffer.from(record.ciphertext),
        Buffer.from(record.iv),
        Buffer.from(record.tag),
        record.wrappedKey,
        record.entityType,
        record.valueHmac,
        record.expiresAt,
      ],
    );
  }

  async get(scope: VaultScope, placeholder: string): Promise<EncryptedVaultRecord | null> {
    const result = await this.sql.query<VaultRow>(
      `SELECT tenant_id, session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type,
              value_hmac, expires_at
       FROM vault_records WHERE tenant_id = $1 AND session_id = $2 AND placeholder = $3`,
      [scope.tenantId, scope.sessionId, placeholder],
    );
    return result.rows[0] === undefined ? null : fromRow(result.rows[0]);
  }

  async getByValueHmac(
    scope: VaultScope,
    entityType: EntityType,
    valueHmac: string,
  ): Promise<EncryptedVaultRecord | null> {
    const result = await this.sql.query<VaultRow>(
      `SELECT tenant_id, session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type,
              value_hmac, expires_at
       FROM vault_records
       WHERE tenant_id = $1 AND session_id = $2 AND entity_type = $3 AND value_hmac = $4
       LIMIT 1`,
      [scope.tenantId, scope.sessionId, entityType, valueHmac],
    );
    return result.rows[0] === undefined ? null : fromRow(result.rows[0]);
  }

  async listSession(scope: VaultScope): Promise<EncryptedVaultRecord[]> {
    const result = await this.sql.query<VaultRow>(
      `SELECT tenant_id, session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type,
              value_hmac, expires_at
       FROM vault_records WHERE tenant_id = $1 AND session_id = $2 ORDER BY placeholder ASC`,
      [scope.tenantId, scope.sessionId],
    );
    return result.rows.map(fromRow);
  }

  async deleteExpired(now: Date): Promise<number> {
    const result = await this.sql.query("DELETE FROM vault_records WHERE expires_at <= $1", [now]);
    return result.rowCount ?? 0;
  }
}

interface VaultRow {
  tenant_id: string;
  session_id: string;
  placeholder: string;
  ciphertext: Uint8Array;
  iv: Uint8Array;
  tag: Uint8Array;
  wrapped_key: string;
  entity_type: EntityType;
  value_hmac: string;
  expires_at: Date | string;
}

function fromRow(row: VaultRow): EncryptedVaultRecord {
  return {
    tenantId: row.tenant_id,
    sessionId: row.session_id,
    placeholder: row.placeholder,
    ciphertext: new Uint8Array(row.ciphertext),
    iv: new Uint8Array(row.iv),
    tag: new Uint8Array(row.tag),
    wrappedKey: row.wrapped_key,
    entityType: row.entity_type,
    valueHmac: row.value_hmac,
    expiresAt: row.expires_at instanceof Date ? row.expires_at : new Date(row.expires_at),
  };
}

function key(scope: VaultScope, placeholder: string): string {
  return `${scope.tenantId}\0${scope.sessionId}\0${placeholder}`;
}

function sessionKey(scope: VaultScope): string {
  return `${scope.tenantId}\0${scope.sessionId}`;
}

function cloneRecord(record: EncryptedVaultRecord): EncryptedVaultRecord {
  return {
    ...record,
    ciphertext: new Uint8Array(record.ciphertext),
    iv: new Uint8Array(record.iv),
    tag: new Uint8Array(record.tag),
    expiresAt: new Date(record.expiresAt),
  };
}
