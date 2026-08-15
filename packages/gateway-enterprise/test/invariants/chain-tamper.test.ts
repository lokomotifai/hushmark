import { expect, it } from "vitest";

import { sha256 } from "../../src/audit/canonical.js";
import { MemoryAuditStore } from "../../src/audit/store.js";
import { verifyAuditChain } from "../../src/audit/verify.js";
import { AuditWriter } from "../../src/audit/writer.js";

it("INV-06 names the first tampered audit sequence", async () => {
  const store = new MemoryAuditStore();
  const writer = new AuditWriter(store, { now: () => new Date("2026-08-09T00:00:00.000Z") });
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
  expect(verifyAuditChain(await store.list())).toEqual({
    ok: true,
    firstBrokenSeq: null,
    verified: 2,
    outOfRange: false,
  });

  const tampered = (await store.list())[0];
  if (tampered === undefined) throw new Error("missing audit record");
  store.unsafeReplace(1, { ...tampered, actor: "attacker" });
  expect(verifyAuditChain(await store.list())).toEqual({
    ok: false,
    firstBrokenSeq: 1,
    verified: 0,
    outOfRange: false,
  });

  expect(verifyAuditChain(await store.list(), 2)).toMatchObject({
    ok: false,
    firstBrokenSeq: 1,
    outOfRange: true,
  });
});

it("rejects a recomputed chain when the audit HMAC key is unavailable to the database writer", async () => {
  const store = new MemoryAuditStore();
  const integrityKey = "test-audit-integrity-key";
  const writer = new AuditWriter(
    store,
    { now: () => new Date("2026-08-09T00:00:00.000Z") },
    integrityKey,
  );
  await writer.append({
    kind: "LOGIN_OK",
    actor: "user:1",
    session_id: null,
    request_sha256: sha256("one"),
    entities: [],
  });
  expect(writer.verify(await store.list()).ok).toBe(true);
  expect(verifyAuditChain(await store.list()).ok).toBe(false);
});
