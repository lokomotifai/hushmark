import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";

import { EnvSchema, loadPolicy } from "@hushmark/gateway";

import { hashSecret, SqlIdentityRepository } from "./admin/identity.js";
import { SqlAdminSessions } from "./admin/session.js";
import { SqlAuditStore } from "./audit/store.js";
import { applyMigrations, PostgresExecutor } from "./db/client.js";
import { AzureKeyVaultKms } from "./kms/azureKeyVault.js";
import { GcpKms } from "./kms/gcpKms.js";
import type { Kms } from "./kms/types.js";
import { VaultTransitKms } from "./kms/vaultTransit.js";
import { SqlPolicyRepository } from "./policy/db.js";
import { buildEnterpriseServer } from "./server.js";
import { retryStartup } from "./startup.js";
import { SqlVaultRepository } from "./vault/repository.js";

const config = EnvSchema.parse(
  Object.fromEntries(Object.keys(EnvSchema.shape).map((key) => [key, process.env[key]])),
);
const staticPolicy = await loadPolicy(config.HUSHMARK_POLICY_PATH);
const databaseUrl = requiredEnv("HUSHMARK_DATABASE_URL");
const licenseFile = requiredEnv("HUSHMARK_LICENSE_FILE");
const keyId = requiredEnv("HUSHMARK_KMS_KEY_ID");
const auditIntegrityKeyFile = requiredEnv("HUSHMARK_AUDIT_HMAC_KEY_FILE");
const auditIntegrityKey = await readIntegrityKey(auditIntegrityKeyFile);
const signedLicense: unknown = JSON.parse(await readFile(licenseFile, "utf8"));
assertEvaluationArtifactsAreExplicit(config.HUSHMARK_API_KEYS, signedLicense);
const executor = new PostgresExecutor(databaseUrl);
await retryStartup(() => applyMigrations(executor), { attempts: 60, delayMs: 1_000 });
const identity = new SqlIdentityRepository(executor);
await retryStartup(() => ensureBootstrapAdmin(identity), { attempts: 60, delayMs: 1_000 });
await ensureBootstrapApiKeys(identity, config.HUSHMARK_API_KEYS);

const publicKeyFile = process.env.HUSHMARK_LICENSE_PUBLIC_KEY_FILE;
const runtime = await buildEnterpriseServer({
  gateway: { config, policy: staticPolicy, logger: true },
  staticPolicy,
  signedLicense,
  identity,
  kms: createKms(),
  keyId,
  ...(publicKeyFile === undefined ? {} : { publicKeyPem: await readFile(publicKeyFile, "utf8") }),
  auditStore: new SqlAuditStore(executor),
  policyRepository: new SqlPolicyRepository(executor),
  vaultRepository: new SqlVaultRepository(executor),
  sessions: new SqlAdminSessions(executor),
  auditIntegrityKey,
  adminSecureCookies: process.env.HUSHMARK_ADMIN_SECURE_COOKIE !== "false",
});
runtime.app.addHook("onClose", () => executor.close());
await runtime.app.listen({
  host: config.HUSHMARK_GATEWAY_HOST,
  port: config.HUSHMARK_GATEWAY_PORT,
});

function createKms(): Kms {
  const kind = requiredEnv("HUSHMARK_KMS_KIND");
  if (kind === "vault") {
    const mount = process.env.HUSHMARK_VAULT_TRANSIT_MOUNT;
    return new VaultTransitKms({
      baseUrl: requiredEnv("HUSHMARK_VAULT_ADDR"),
      token: requiredEnv("HUSHMARK_VAULT_TOKEN"),
      ...(mount === undefined ? {} : { mount }),
    });
  }
  if (kind === "azure") return new AzureKeyVaultKms();
  if (kind === "gcp") return new GcpKms();
  throw new Error("HUSHMARK_KMS_KIND must be vault, azure, or gcp");
}

async function ensureBootstrapAdmin(identityRepository: SqlIdentityRepository): Promise<void> {
  const email = requiredEnv("HUSHMARK_ADMIN_EMAIL");
  if ((await identityRepository.findUserByEmail(email)) !== null) return;
  await identityRepository.putUser({
    id: randomUUID(),
    email,
    passwordHash: await hashSecret(requiredEnv("HUSHMARK_ADMIN_PASSWORD")),
    role: "admin",
    enabled: true,
  });
}

async function ensureBootstrapApiKeys(
  identityRepository: SqlIdentityRepository,
  secrets: readonly string[],
): Promise<void> {
  const existingPrefixes = new Set(
    (await identityRepository.listApiKeys()).map((record) => record.prefix),
  );
  for (const [index, secret] of secrets.entries()) {
    const prefix = secret.slice(0, 18);
    if (existingPrefixes.has(prefix)) continue;
    await identityRepository.putApiKey(
      {
        id: randomUUID(),
        name: `bootstrap-${String(index + 1)}`,
        prefix,
        revokedAt: null,
        createdAt: new Date().toISOString(),
      },
      await hashSecret(secret),
    );
    existingPrefixes.add(prefix);
  }
}

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) throw new Error(`${name} is required`);
  return value;
}

async function readIntegrityKey(path: string): Promise<Buffer> {
  const key = await readFile(path);
  if (key.byteLength < 32) throw new Error("audit HMAC key must contain at least 32 bytes");
  return key;
}

function assertEvaluationArtifactsAreExplicit(
  apiKeys: readonly string[],
  signedLicense: unknown,
): void {
  const evaluationLicense =
    typeof signedLicense === "object" &&
    signedLicense !== null &&
    "licensee" in signedLicense &&
    signedLicense.licensee === "Hushmark local evaluation";
  const evaluationCredentialPresent =
    apiKeys.some((key) => key.includes("evaluation")) ||
    process.env.HUSHMARK_ADMIN_PASSWORD?.includes("evaluation") === true ||
    process.env.HUSHMARK_VAULT_TOKEN?.includes("evaluation") === true;
  if (
    (evaluationCredentialPresent || evaluationLicense) &&
    process.env.HUSHMARK_EVALUATION_MODE !== "true"
  ) {
    throw new Error("evaluation artifacts require HUSHMARK_EVALUATION_MODE=true");
  }
}
