import type { MaskEvent } from "@hushmark/gateway";

import { auditHash, GENESIS_HASH, sha256 } from "./canonical.js";
import type { AuditStore } from "./store.js";
import { AuditInputSchema, type AuditInput, type AuditRecord } from "./types.js";
import { verifyAuditChain, type VerifyResult } from "./verify.js";

export interface Clock {
  now(): Date;
}

export const systemClock: Clock = { now: () => new Date() };

export class AuditWriter {
  #queue: Promise<unknown> = Promise.resolve();

  constructor(
    private readonly store: AuditStore,
    private readonly clock: Clock = systemClock,
    private readonly integrityKey?: string | Uint8Array,
  ) {}

  append(input: Omit<AuditInput, "ts"> & { ts?: string }): Promise<AuditRecord> {
    const task = this.#queue.then(async () => {
      const parsed = AuditInputSchema.parse({
        ...input,
        ts: input.ts ?? this.clock.now().toISOString(),
      });
      if (this.store.appendLinked !== undefined) {
        return this.store.appendLinked(parsed, this.integrityKey);
      }
      const previous = await this.store.latest();
      const withoutHash = {
        ...parsed,
        seq: (previous?.seq ?? 0) + 1,
        prev_hash: previous?.hash ?? GENESIS_HASH,
      };
      const record: AuditRecord = {
        ...withoutHash,
        hash: auditHash(withoutHash, this.integrityKey),
      };
      await this.store.append(record);
      return record;
    });
    this.#queue = task.catch(() => undefined);
    return task;
  }

  verify(
    records: readonly AuditRecord[],
    from = 1,
    to: number | "latest" = "latest",
  ): VerifyResult {
    return verifyAuditChain(records, from, to, this.integrityKey);
  }

  appendMaskEvent(event: MaskEvent): Promise<AuditRecord> {
    return this.append({
      kind: "MASK_APPLIED",
      actor: `api-key:${event.tenant_id}`,
      session_id: event.session_id,
      request_sha256: sha256(
        JSON.stringify(event.entities.map(({ type, action, count }) => ({ type, action, count }))),
      ),
      entities: event.entities,
    });
  }

  appendAnchor(date: string): Promise<AuditRecord> {
    return this.append({
      kind: "ANCHOR",
      actor: "system:audit",
      session_id: null,
      request_sha256: sha256(date),
      entities: [],
    });
  }
}
