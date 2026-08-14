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

function cloneRecord(record: EncryptedVaultRecord): EncryptedVaultRecord {
  return {
    ...record,
    ciphertext: new Uint8Array(record.ciphertext),
    iv: new Uint8Array(record.iv),
    tag: new Uint8Array(record.tag),
    expiresAt: new Date(record.expiresAt),
  };
}
