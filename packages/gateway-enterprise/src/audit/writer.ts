import type { MaskEvent } from "@hushmark/gateway";

import { auditHash, GENESIS_HASH, sha256 } from "./canonical.js";
import type { AuditStore } from "./store.js";
import { AuditInputSchema, type AuditInput, type AuditRecord } from "./types.js";

export interface Clock {
  now(): Date;
}

export const systemClock: Clock = { now: () => new Date() };

export class AuditWriter {
  #queue: Promise<unknown> = Promise.resolve();

  constructor(
    private readonly store: AuditStore,
    private readonly clock: Clock = systemClock,
  ) {}

  append(input: Omit<AuditInput, "ts"> & { ts?: string }): Promise<AuditRecord> {
    const task = this.#queue.then(async () => {
      const records = await this.store.list();
      const previous = records.at(-1);
      const parsed = AuditInputSchema.parse({
        ...input,
        ts: input.ts ?? this.clock.now().toISOString(),
      });
      const withoutHash = {
        ...parsed,
        seq: (previous?.seq ?? 0) + 1,
        prev_hash: previous?.hash ?? GENESIS_HASH,
      };
      const record: AuditRecord = { ...withoutHash, hash: auditHash(withoutHash) };
      await this.store.append(record);
      return record;
    });
    this.#queue = task.catch(() => undefined);
    return task;
  }

  appendMaskEvent(event: MaskEvent): Promise<AuditRecord> {
    return this.append({
      kind: "MASK_APPLIED",
      actor: "system:gateway",
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
