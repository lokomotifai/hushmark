import { auditHash, GENESIS_HASH } from "./canonical.js";
import { AuditInputSchema, AuditRecordSchema, type AuditInput, type AuditRecord } from "./types.js";
import type { SqlExecutor } from "../db/client.js";

export interface AuditStore {
  list(): Promise<AuditRecord[]>;
  page(offset: number, limit: number): Promise<{ records: AuditRecord[]; total: number }>;
  metrics(): Promise<{
    masked: number;
    blocked: number;
    entityCounts: Record<string, number>;
  }>;
  latest(): Promise<AuditRecord | null>;
  append(record: AuditRecord): Promise<void>;
  appendLinked?(input: AuditInput, integrityKey?: string | Uint8Array): Promise<AuditRecord>;
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

  latest(): Promise<AuditRecord | null> {
    const record = this.#records.at(-1);
    return Promise.resolve(record === undefined ? null : structuredClone(record));
  }

  page(offset: number, limit: number): Promise<{ records: AuditRecord[]; total: number }> {
    const records = [...this.#records].reverse().slice(offset, offset + limit);
    return Promise.resolve({ records: structuredClone(records), total: this.#records.length });
  }

  metrics(): Promise<{
    masked: number;
    blocked: number;
    entityCounts: Record<string, number>;
  }> {
    const entityCounts: Record<string, number> = {};
    let masked = 0;
    let blocked = 0;
    for (const event of this.#records) {
      if (event.kind === "MASK_APPLIED") masked += 1;
      if (event.kind === "REQUEST_BLOCKED") blocked += 1;
      for (const entity of event.entities) {
        entityCounts[entity.type] = (entityCounts[entity.type] ?? 0) + entity.count;
      }
    }
    return Promise.resolve({ masked, blocked, entityCounts });
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

  async latest(): Promise<AuditRecord | null> {
    const result = await this.sql.query<AuditRow>(
      `SELECT seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash
       FROM audit_events ORDER BY seq DESC LIMIT 1`,
    );
    return result.rows[0] === undefined ? null : fromAuditRow(result.rows[0]);
  }

  async page(offset: number, limit: number): Promise<{ records: AuditRecord[]; total: number }> {
    const [recordsResult, countResult] = await Promise.all([
      this.sql.query<AuditRow>(
        `SELECT seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash
         FROM audit_events ORDER BY seq DESC LIMIT $1 OFFSET $2`,
        [limit, offset],
      ),
      this.sql.query<{ total: string | number }>("SELECT COUNT(*) AS total FROM audit_events"),
    ]);
    return {
      records: recordsResult.rows.map(fromAuditRow),
      total: Number(countResult.rows[0]?.total ?? 0),
    };
  }

  async metrics(): Promise<{
    masked: number;
    blocked: number;
    entityCounts: Record<string, number>;
  }> {
    const [eventsResult, entitiesResult] = await Promise.all([
      this.sql.query<{ masked: string | number; blocked: string | number }>(
        `SELECT
           COUNT(*) FILTER (WHERE kind = 'MASK_APPLIED') AS masked,
           COUNT(*) FILTER (WHERE kind = 'REQUEST_BLOCKED') AS blocked
         FROM audit_events`,
      ),
      this.sql.query<{ type: string; count: string | number }>(
        `SELECT entity->>'type' AS type, SUM((entity->>'count')::integer) AS count
         FROM audit_events CROSS JOIN LATERAL jsonb_array_elements(entities) AS entity
         GROUP BY entity->>'type'`,
      ),
    ]);
    return {
      masked: Number(eventsResult.rows[0]?.masked ?? 0),
      blocked: Number(eventsResult.rows[0]?.blocked ?? 0),
      entityCounts: Object.fromEntries(
        entitiesResult.rows.map((row) => [row.type, Number(row.count)]),
      ),
    };
  }

  async append(record: AuditRecord): Promise<void> {
    const parsed = AuditRecordSchema.parse(record);
    await this.sql.query(
      `INSERT INTO audit_events
       (seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash)
       VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)`,
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

  async appendLinked(input: AuditInput, integrityKey?: string | Uint8Array): Promise<AuditRecord> {
    if (this.sql.transaction === undefined) {
      throw new Error("SQL audit store requires transactional executor support");
    }
    return this.sql.transaction(async (transaction) => {
      await transaction.query("SELECT pg_advisory_xact_lock($1)", [1_214_839_721]);
      const previousResult = await transaction.query<AuditRow>(
        `SELECT seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash
         FROM audit_events ORDER BY seq DESC LIMIT 1`,
      );
      const previous =
        previousResult.rows[0] === undefined ? null : fromAuditRow(previousResult.rows[0]);
      const withoutHash = {
        ...AuditInputSchema.parse(input),
        seq: (previous?.seq ?? 0) + 1,
        prev_hash: previous?.hash ?? GENESIS_HASH,
      };
      const record = AuditRecordSchema.parse({
        ...withoutHash,
        hash: auditHash(withoutHash, integrityKey),
      });
      await appendWithExecutor(transaction, record);
      return record;
    });
  }
}

interface AuditRow {
  seq: string | number;
  ts: Date | string;
  kind: string;
  actor: string;
  session_id: string | null;
  request_sha256: string;
  entities: unknown;
  prev_hash: string;
  hash: string;
}

function fromAuditRow(row: AuditRow): AuditRecord {
  return AuditRecordSchema.parse({
    ...row,
    seq: Number(row.seq),
    ts: row.ts instanceof Date ? row.ts.toISOString() : row.ts,
  });
}

async function appendWithExecutor(sql: SqlExecutor, record: AuditRecord): Promise<void> {
  await sql.query(
    `INSERT INTO audit_events
     (seq, ts, kind, actor, session_id, request_sha256, entities, prev_hash, hash)
     VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)`,
    [
      record.seq,
      record.ts,
      record.kind,
      record.actor,
      record.session_id,
      record.request_sha256,
      JSON.stringify(record.entities),
      record.prev_hash,
      record.hash,
    ],
  );
}
