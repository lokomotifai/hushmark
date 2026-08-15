import { readFile } from "node:fs/promises";

import { PostgresExecutor } from "./db/client.js";
import { SqlAuditStore } from "./audit/store.js";
import { AuditRecordSchema, type AuditRecord } from "./audit/types.js";
import { verifyAuditChain } from "./audit/verify.js";

const options = parseOptions(process.argv.slice(2));
const records = await loadRecords();
const integrityKeyFile = process.env.HUSHMARK_AUDIT_HMAC_KEY_FILE;
const integrityKey =
  integrityKeyFile === undefined ? undefined : await readIntegrityKey(integrityKeyFile);
const result = verifyAuditChain(records, options.from, options.to, integrityKey);
if (!result.ok) {
  process.stderr.write(`audit chain broken at seq ${String(result.firstBrokenSeq)}\n`);
  process.exitCode = 1;
} else {
  process.stdout.write(`audit chain verified: ${String(result.verified)} events\n`);
}

async function readIntegrityKey(path: string): Promise<Buffer> {
  const key = await readFile(path);
  if (key.byteLength < 32) throw new Error("audit HMAC key must contain at least 32 bytes");
  return key;
}

async function loadRecords(): Promise<AuditRecord[]> {
  const file = process.env.HUSHMARK_AUDIT_FILE;
  if (file !== undefined) {
    const lines = (await readFile(file, "utf8")).split(/\r?\n/u).filter((line) => line.length > 0);
    return lines.map((line) => AuditRecordSchema.parse(JSON.parse(line)));
  }
  const databaseUrl = process.env.HUSHMARK_DATABASE_URL;
  if (databaseUrl === undefined) {
    throw new Error("HUSHMARK_DATABASE_URL or HUSHMARK_AUDIT_FILE is required");
  }
  const executor = new PostgresExecutor(databaseUrl);
  try {
    return await new SqlAuditStore(executor).list();
  } finally {
    await executor.close();
  }
}

function parseOptions(args: string[]): { from: number; to: number | "latest" } {
  let from = 1;
  let to: number | "latest" = "latest";
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    const value = args[index + 1];
    if (argument === "--from" && value !== undefined) {
      from = positiveInteger(value, "from");
      index += 1;
    } else if (argument === "--to" && value !== undefined) {
      to = value === "latest" ? "latest" : positiveInteger(value, "to");
      index += 1;
    } else {
      throw new Error(`unknown audit-verify argument: ${argument ?? "<missing>"}`);
    }
  }
  return { from, to };
}

function positiveInteger(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1)
    throw new Error(`${label} must be a positive integer`);
  return parsed;
}
