import { auditHash, GENESIS_HASH } from "./canonical.js";
import { AuditRecordSchema, type AuditRecord } from "./types.js";
import type { AuditCheckpoint } from "./checkpoint.js";

export interface VerifyResult {
  ok: boolean;
  firstBrokenSeq: number | null;
  verified: number;
  outOfRange: boolean;
}

export function verifyAuditChain(
  input: readonly AuditRecord[],
  from = 1,
  to: number | "latest" = "latest",
  integrityKey: string | Uint8Array,
  checkpoint?: AuditCheckpoint | null,
): VerifyResult {
  const records = input.map((record) => AuditRecordSchema.parse(record));
  const upper = to === "latest" ? Number.POSITIVE_INFINITY : to;
  let previousHash = GENESIS_HASH;
  let expectedSeq = 1;
  let verified = 0;
  for (const record of records) {
    const expectedHash = auditHash(
      {
        seq: record.seq,
        ts: record.ts,
        kind: record.kind,
        actor: record.actor,
        session_id: record.session_id,
        request_sha256: record.request_sha256,
        entities: record.entities,
        prev_hash: record.prev_hash,
      },
      integrityKey,
    );
    const broken =
      record.seq !== expectedSeq ||
      record.prev_hash !== previousHash ||
      record.hash !== expectedHash;
    if (broken) {
      return {
        ok: false,
        firstBrokenSeq: record.seq,
        verified,
        outOfRange: record.seq < from || record.seq > upper,
      };
    }
    if (record.seq >= from && record.seq <= upper) verified += 1;
    previousHash = record.hash;
    expectedSeq += 1;
  }
  const latest = records.at(-1);
  if (checkpoint !== undefined && checkpoint !== null) {
    const anchored = records[checkpoint.seq - 1];
    if (anchored?.hash !== checkpoint.hash || latest?.seq !== checkpoint.seq) {
      const firstBrokenSeq =
        latest === undefined || latest.seq < checkpoint.seq
          ? (latest?.seq ?? 0) + 1
          : checkpoint.seq + 1;
      return {
        ok: false,
        firstBrokenSeq,
        verified,
        outOfRange: firstBrokenSeq < from || firstBrokenSeq > upper,
      };
    }
  }
  return { ok: true, firstBrokenSeq: null, verified, outOfRange: false };
}

export function auditNdjson(records: readonly AuditRecord[]): string {
  return records.map((record) => JSON.stringify(AuditRecordSchema.parse(record))).join("\n") + "\n";
}
