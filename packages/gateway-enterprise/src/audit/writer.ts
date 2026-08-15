import type { MaskEvent } from "@hushmark/gateway";

import { assertIntegrityKey, type AuditCheckpointStore } from "./checkpoint.js";
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
  #initialization: Promise<void> | undefined;

  constructor(
    private readonly store: AuditStore,
    private readonly integrityKey: string | Uint8Array,
    private readonly checkpoints: AuditCheckpointStore,
    private readonly clock: Clock = systemClock,
    private readonly allowCheckpointBootstrap = false,
  ) {
    assertIntegrityKey(integrityKey);
  }

  append(input: Omit<AuditInput, "ts"> & { ts?: string }): Promise<AuditRecord> {
    const task = this.#queue.then(async () => {
      await this.#initialize();
      const parsed = AuditInputSchema.parse({
        ...input,
        ts: input.ts ?? this.clock.now().toISOString(),
      });
      const record =
        this.store.appendLinked !== undefined
          ? await this.store.appendLinked(parsed, this.integrityKey)
          : await this.#appendWithoutTransaction(parsed);
      try {
        await this.checkpoints.advance({ seq: record.seq, hash: record.hash });
      } catch (error) {
        this.#initialization = undefined;
        throw error;
      }
      return record;
    });
    this.#queue = task.catch(() => undefined);
    return task;
  }

  async verify(
    records: readonly AuditRecord[],
    from = 1,
    to: number | "latest" = "latest",
  ): Promise<VerifyResult> {
    await this.#initialize();
    return verifyAuditChain(records, from, to, this.integrityKey, await this.checkpoints.read());
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

  async #initialize(): Promise<void> {
    this.#initialization ??= this.#reconcileCheckpoint();
    return this.#initialization;
  }

  async #reconcileCheckpoint(): Promise<void> {
    const records = await this.store.list();
    const chain = verifyAuditChain(records, 1, "latest", this.integrityKey);
    if (!chain.ok) {
      throw new Error(`audit chain integrity failed at seq ${String(chain.firstBrokenSeq)}`);
    }
    const checkpoint = await this.checkpoints.read();
    const latest = records.at(-1);
    if (checkpoint !== null) {
      const anchored = records[checkpoint.seq - 1];
      if (anchored?.hash !== checkpoint.hash) {
        throw new Error("audit database does not contain the externally checkpointed head");
      }
    } else if (latest !== undefined && !this.allowCheckpointBootstrap) {
      throw new Error("existing audit records require explicit external checkpoint bootstrap");
    }
    if (latest !== undefined && (checkpoint === null || latest.seq > checkpoint.seq)) {
      await this.checkpoints.advance({ seq: latest.seq, hash: latest.hash });
    }
  }

  async #appendWithoutTransaction(input: AuditInput): Promise<AuditRecord> {
    const previous = await this.store.latest();
    const withoutHash = {
      ...input,
      seq: (previous?.seq ?? 0) + 1,
      prev_hash: previous?.hash ?? GENESIS_HASH,
    };
    const record: AuditRecord = {
      ...withoutHash,
      hash: auditHash(withoutHash, this.integrityKey),
    };
    await this.store.append(record);
    return record;
  }
}
