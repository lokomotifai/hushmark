import { mkdtemp, open, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, expect, it } from "vitest";

import { FileAuditCheckpointStore } from "../../src/audit/checkpoint.js";

const temporaryDirectories: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryDirectories.splice(0).map((path) => rm(path, { recursive: true, force: true })),
  );
});

it("persists an authenticated append-only checkpoint with owner-only permissions", async () => {
  const directory = await mkdtemp(join(tmpdir(), "hushmark-audit-checkpoint-"));
  temporaryDirectories.push(directory);
  const path = join(directory, "checkpoint.jsonl");
  const store = new FileAuditCheckpointStore(path, new Uint8Array(32).fill(4));
  const checkpoint = { seq: 7, hash: "a".repeat(64) };

  expect(await store.read()).toBeNull();
  await store.advance(checkpoint);
  expect(await store.read()).toEqual(checkpoint);
  const file = await open(path, "r+");
  const content = await file.readFile("utf8");
  expect((await file.stat()).mode & 0o777).toBe(0o600);
  const tampered = content.replace(/"mac":"[a-f0-9]+"/u, `"mac":"${"0".repeat(64)}"`);
  await file.truncate(0);
  await file.write(tampered, 0, "utf8");
  await file.sync();
  await file.close();
  await expect(store.read()).rejects.toThrow("audit checkpoint authentication failed");
});
