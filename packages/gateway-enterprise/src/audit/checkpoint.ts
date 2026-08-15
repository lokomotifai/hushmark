import { createHmac, timingSafeEqual } from "node:crypto";
import { open, readFile } from "node:fs/promises";

import { z } from "zod";

const HashSchema = z.string().regex(/^[a-f0-9]{64}$/u);
const CheckpointLineSchema = z
  .object({
    v: z.literal(1),
    seq: z.number().int().positive(),
    hash: HashSchema,
    mac: HashSchema,
  })
  .strict();

export interface AuditCheckpoint {
  seq: number;
  hash: string;
}

export interface AuditCheckpointStore {
  read(): Promise<AuditCheckpoint | null>;
  advance(checkpoint: AuditCheckpoint): Promise<void>;
}

export class MemoryAuditCheckpointStore implements AuditCheckpointStore {
  #checkpoint: AuditCheckpoint | null = null;

  read(): Promise<AuditCheckpoint | null> {
    return Promise.resolve(this.#checkpoint === null ? null : { ...this.#checkpoint });
  }

  advance(checkpoint: AuditCheckpoint): Promise<void> {
    validateCheckpoint(checkpoint);
    if (this.#checkpoint?.seq === checkpoint.seq && this.#checkpoint.hash !== checkpoint.hash) {
      throw new Error("audit checkpoint hash conflicts with the current head");
    }
    if (this.#checkpoint === null || checkpoint.seq > this.#checkpoint.seq) {
      this.#checkpoint = { ...checkpoint };
    }
    return Promise.resolve();
  }
}

export class FileAuditCheckpointStore implements AuditCheckpointStore {
  constructor(
    private readonly path: string,
    private readonly integrityKey: string | Uint8Array,
  ) {
    assertIntegrityKey(integrityKey);
  }

  async read(): Promise<AuditCheckpoint | null> {
    let content: string;
    try {
      content = await readFile(this.path, "utf8");
    } catch (error) {
      if (isNodeError(error) && error.code === "ENOENT") return null;
      throw error;
    }
    let head: AuditCheckpoint | null = null;
    for (const line of content.split(/\r?\n/u).filter((value) => value.length > 0)) {
      const parsed = CheckpointLineSchema.parse(JSON.parse(line));
      const expected = checkpointMac(parsed, this.integrityKey);
      const actualBytes = Buffer.from(parsed.mac, "hex");
      const expectedBytes = Buffer.from(expected, "hex");
      if (!timingSafeEqual(actualBytes, expectedBytes)) {
        throw new Error("audit checkpoint authentication failed");
      }
      head = selectHead(head, { seq: parsed.seq, hash: parsed.hash });
    }
    return head;
  }

  async advance(checkpoint: AuditCheckpoint): Promise<void> {
    validateCheckpoint(checkpoint);
    const current = await this.read();
    if (current?.seq === checkpoint.seq && current.hash !== checkpoint.hash) {
      throw new Error("audit checkpoint hash conflicts with the current head");
    }
    if (current !== null && checkpoint.seq <= current.seq) return;
    const line = {
      v: 1 as const,
      ...checkpoint,
      mac: checkpointMac(checkpoint, this.integrityKey),
    };
    const file = await open(this.path, "a", 0o600);
    try {
      await file.writeFile(`${JSON.stringify(line)}\n`, "utf8");
      await file.sync();
    } finally {
      await file.close();
    }
  }
}

function checkpointMac(
  checkpoint: Pick<AuditCheckpoint, "seq" | "hash">,
  integrityKey: string | Uint8Array,
): string {
  return createHmac("sha256", integrityKey)
    .update(`hushmark-audit-checkpoint-v1\0${String(checkpoint.seq)}\0${checkpoint.hash}`)
    .digest("hex");
}

function validateCheckpoint(checkpoint: AuditCheckpoint): void {
  z.object({ seq: z.number().int().positive(), hash: HashSchema }).strict().parse(checkpoint);
}

function selectHead(current: AuditCheckpoint | null, candidate: AuditCheckpoint): AuditCheckpoint {
  if (current?.seq === candidate.seq && current.hash !== candidate.hash) {
    throw new Error("audit checkpoint log contains conflicting heads");
  }
  return current === null || candidate.seq > current.seq ? candidate : current;
}

export function assertIntegrityKey(integrityKey: string | Uint8Array): void {
  if (Buffer.byteLength(integrityKey) < 32) {
    throw new Error("audit HMAC key must contain at least 32 bytes");
  }
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
