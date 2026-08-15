import { createHash, createHmac } from "node:crypto";

import canonicalize from "canonicalize";

import type { AuditRecord } from "./types.js";

export const GENESIS_HASH = sha256("hushmark-genesis-v1");

export function jcs(value: unknown): string {
  const result = canonicalize(value);
  if (result === undefined) throw new TypeError("value is not valid canonical JSON");
  return result;
}

export function sha256(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

export function auditHash(
  eventWithoutHash: Omit<AuditRecord, "hash">,
  integrityKey: string | Uint8Array,
): string {
  const canonical = jcs(eventWithoutHash) + eventWithoutHash.prev_hash;
  return createHmac("sha256", integrityKey).update(canonical).digest("hex");
}
