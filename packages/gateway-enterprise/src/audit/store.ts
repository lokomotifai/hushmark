import { AuditRecordSchema, type AuditRecord } from "./types.js";
import type { SqlExecutor } from "../db/client.js";

export interface AuditStore {
  list(): Promise<AuditRecord[]>;
  append(record: AuditRecord): Promise<void>;
}

export class MemoryAuditStore implements AuditStore {
  readonly #records: AuditRecord[] = [];

  list(): Promise<AuditRecord[]> {
    return Promise.resolve(structuredClone(this.#records));
  }

  append(record: AuditRecord): Promise<void> {
    this.#records.push(structuredClone(AuditRecordSchema.parse(record)));
    return Promise.resolve();
  }

  unsafeReplace(seq: number, replacement: AuditRecord): void {
    const index = this.#records.findIndex((record) => record.seq === seq);
    if (index < 0) throw new RangeError(`unknown audit seq ${String(seq)}`);
    this.#records[index] = structuredClone(replacement);
  }
}

export class SqlAuditStore implements AuditStore {
  constructor(private readonly sql: SqlExecutor) {}

  async list(): Promise<AuditRecord[]> {
    const result = await this.sql.query<{
      seq: string | number;
      ts: Date | string;
      kind: string;
      actor: string;
      session_id: string | null;
      request_sha256: string;
      entities: unknown;
      prev_hash: string;
      hash: string;
    }>(
      `SELECT seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash
       FROM audit_events ORDER BY seq ASC`,
    );
    return result.rows.map((row) =>
      AuditRecordSchema.parse({
        ...row,
        seq: Number(row.seq),
        ts: row.ts instanceof Date ? row.ts.toISOString() : row.ts,
      }),
    );
  }

  async append(record: AuditRecord): Promise<void> {
    const parsed = AuditRecordSchema.parse(record);
    await this.sql.query(
      `INSERT INTO audit_events
       (seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash)
       OVERRIDING SYSTEM VALUE VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)`,
      [
        parsed.seq,
        parsed.ts,
        parsed.kind,
        parsed.actor,
        parsed.session_id,
        parsed.request_sha256,
        JSON.stringify(parsed.entities),
        parsed.prev_hash,
        parsed.hash,
      ],
    );
  }
}
