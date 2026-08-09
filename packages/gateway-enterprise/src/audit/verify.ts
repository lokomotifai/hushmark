import { auditHash, GENESIS_HASH } from "./canonical.js";
import { AuditRecordSchema, type AuditRecord } from "./types.js";

export interface VerifyResult {
  ok: boolean;
  firstBrokenSeq: number | null;
  verified: number;
}

export function verifyAuditChain(
  input: readonly AuditRecord[],
  from = 1,
  to: number | "latest" = "latest",
): VerifyResult {
  const records = input.map((record) => AuditRecordSchema.parse(record));
  const upper = to === "latest" ? Number.POSITIVE_INFINITY : to;
  let previousHash = GENESIS_HASH;
  let expectedSeq = 1;
  let verified = 0;
  for (const record of records) {
    const expectedHash = auditHash({
      seq: record.seq,
      ts: record.ts,
      kind: record.kind,
      actor: record.actor,
      session_id: record.session_id,
      request_sha256: record.request_sha256,
      entities: record.entities,
      prev_hash: record.prev_hash,
    });
    const broken =
      record.seq !== expectedSeq ||
      record.prev_hash !== previousHash ||
      record.hash !== expectedHash;
    if (broken && record.seq >= from && record.seq <= upper) {
      return { ok: false, firstBrokenSeq: record.seq, verified };
    }
    if (record.seq >= from && record.seq <= upper) verified += 1;
    previousHash = record.hash;
    expectedSeq += 1;
    if (record.seq >= upper) break;
  }
  return { ok: true, firstBrokenSeq: null, verified };
}

export function auditNdjson(records: readonly AuditRecord[]): string {
  return records.map((record) => JSON.stringify(AuditRecordSchema.parse(record))).join("\n") + "\n";
}
