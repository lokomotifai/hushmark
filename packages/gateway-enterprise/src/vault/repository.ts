import type { EntityType } from "@hushmark/shared";

import type { SqlExecutor } from "../db/client.js";

export interface EncryptedVaultRecord {
  sessionId: string;
  placeholder: string;
  ciphertext: Uint8Array;
  iv: Uint8Array;
  tag: Uint8Array;
  wrappedKey: string;
  entityType: EntityType;
  expiresAt: Date;
}

export interface VaultRepository {
  put(record: EncryptedVaultRecord): Promise<void>;
  get(sessionId: string, placeholder: string): Promise<EncryptedVaultRecord | null>;
  listSession(sessionId: string): Promise<EncryptedVaultRecord[]>;
  deleteExpired(now: Date): Promise<number>;
}

export class MemoryVaultRepository implements VaultRepository {
  readonly #records = new Map<string, EncryptedVaultRecord>();

  put(record: EncryptedVaultRecord): Promise<void> {
    this.#records.set(key(record.sessionId, record.placeholder), cloneRecord(record));
    return Promise.resolve();
  }

  get(sessionId: string, placeholder: string): Promise<EncryptedVaultRecord | null> {
    const record = this.#records.get(key(sessionId, placeholder));
    return Promise.resolve(record === undefined ? null : cloneRecord(record));
  }

  listSession(sessionId: string): Promise<EncryptedVaultRecord[]> {
    return Promise.resolve(
      [...this.#records.values()]
        .filter((record) => record.sessionId === sessionId)
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
       (session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type, expires_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
       ON CONFLICT (session_id, placeholder) DO UPDATE SET ciphertext = EXCLUDED.ciphertext,
       iv = EXCLUDED.iv, tag = EXCLUDED.tag, wrapped_key = EXCLUDED.wrapped_key,
       entity_type = EXCLUDED.entity_type, expires_at = EXCLUDED.expires_at`,
      [
        record.sessionId,
        record.placeholder,
        Buffer.from(record.ciphertext),
        Buffer.from(record.iv),
        Buffer.from(record.tag),
        record.wrappedKey,
        record.entityType,
        record.expiresAt,
      ],
    );
  }

  async get(sessionId: string, placeholder: string): Promise<EncryptedVaultRecord | null> {
    const result = await this.sql.query<VaultRow>(
      `SELECT session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type, expires_at
       FROM vault_records WHERE session_id = $1 AND placeholder = $2`,
      [sessionId, placeholder],
    );
    return result.rows[0] === undefined ? null : fromRow(result.rows[0]);
  }

  async listSession(sessionId: string): Promise<EncryptedVaultRecord[]> {
    const result = await this.sql.query<VaultRow>(
      `SELECT session_id, placeholder, ciphertext, iv, tag, wrapped_key, entity_type, expires_at
       FROM vault_records WHERE session_id = $1 ORDER BY placeholder ASC`,
      [sessionId],
    );
    return result.rows.map(fromRow);
  }

  async deleteExpired(now: Date): Promise<number> {
    const result = await this.sql.query("DELETE FROM vault_records WHERE expires_at <= $1", [now]);
    return result.rowCount ?? 0;
  }
}

interface VaultRow {
  session_id: string;
  placeholder: string;
  ciphertext: Uint8Array;
  iv: Uint8Array;
  tag: Uint8Array;
  wrapped_key: string;
  entity_type: EntityType;
  expires_at: Date | string;
}

function fromRow(row: VaultRow): EncryptedVaultRecord {
  return {
    sessionId: row.session_id,
    placeholder: row.placeholder,
    ciphertext: new Uint8Array(row.ciphertext),
    iv: new Uint8Array(row.iv),
    tag: new Uint8Array(row.tag),
    wrappedKey: row.wrapped_key,
    entityType: row.entity_type,
    expiresAt: row.expires_at instanceof Date ? row.expires_at : new Date(row.expires_at),
  };
}

function key(session: string, placeholder: string): string {
  return `${session}\0${placeholder}`;
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
