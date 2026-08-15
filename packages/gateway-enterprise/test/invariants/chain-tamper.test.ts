import { expect, it } from "vitest";

import { MemoryAuditCheckpointStore } from "../../src/audit/checkpoint.js";
import { sha256 } from "../../src/audit/canonical.js";
import { MemoryAuditStore } from "../../src/audit/store.js";
import { verifyAuditChain } from "../../src/audit/verify.js";
import { AuditWriter } from "../../src/audit/writer.js";

it("INV-06 names the first tampered audit sequence", async () => {
  const store = new MemoryAuditStore();
  const integrityKey = new Uint8Array(32).fill(7);
  const checkpoints = new MemoryAuditCheckpointStore();
  const writer = new AuditWriter(store, integrityKey, checkpoints, {
    now: () => new Date("2026-08-09T00:00:00.000Z"),
  });
  await writer.append({
    kind: "LOGIN_OK",
    actor: "user:1",
    session_id: null,
    request_sha256: sha256("one"),
    entities: [],
  });
  await writer.append({
    kind: "POLICY_CHANGED",
    actor: "user:1",
    session_id: null,
    request_sha256: sha256("two"),
    entities: [],
  });
  expect(
    verifyAuditChain(await store.list(), 1, "latest", integrityKey, await checkpoints.read()),
  ).toEqual({
    ok: true,
    firstBrokenSeq: null,
    verified: 2,
    outOfRange: false,
  });

  const tampered = (await store.list())[0];
  if (tampered === undefined) throw new Error("missing audit record");
  store.unsafeReplace(1, { ...tampered, actor: "attacker" });
  expect(verifyAuditChain(await store.list(), 1, "latest", integrityKey)).toEqual({
    ok: false,
    firstBrokenSeq: 1,
    verified: 0,
    outOfRange: false,
  });

  expect(verifyAuditChain(await store.list(), 2, "latest", integrityKey)).toMatchObject({
    ok: false,
    firstBrokenSeq: 1,
    outOfRange: true,
  });
});

it("rejects a recomputed chain when the audit HMAC key is unavailable to the database writer", async () => {
  const store = new MemoryAuditStore();
  const integrityKey = "test-audit-integrity-key-at-least-32-bytes";
  const checkpoints = new MemoryAuditCheckpointStore();
  const writer = new AuditWriter(store, integrityKey, checkpoints, {
    now: () => new Date("2026-08-09T00:00:00.000Z"),
  });
  await writer.append({
    kind: "LOGIN_OK",
    actor: "user:1",
    session_id: null,
    request_sha256: sha256("one"),
    entities: [],
  });
  expect((await writer.verify(await store.list())).ok).toBe(true);
  expect(
    verifyAuditChain(await store.list(), 1, "latest", "wrong-audit-integrity-key-at-least-32-bytes")
      .ok,
  ).toBe(false);
});

it("rejects a valid HMAC chain whose externally checkpointed tail was deleted", async () => {
  const store = new MemoryAuditStore();
  const integrityKey = new Uint8Array(32).fill(5);
  const checkpoints = new MemoryAuditCheckpointStore();
  const writer = new AuditWriter(store, integrityKey, checkpoints);
  for (const value of ["one", "two"]) {
    await writer.append({
      kind: "LOGIN_OK",
      actor: "user:1",
      session_id: null,
      request_sha256: sha256(value),
      entities: [],
    });
  }
  const truncated = (await store.list()).slice(0, 1);
  expect(
    verifyAuditChain(truncated, 1, "latest", integrityKey, await checkpoints.read()),
  ).toMatchObject({ ok: false, firstBrokenSeq: 2 });
});
