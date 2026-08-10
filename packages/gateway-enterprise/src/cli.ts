import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";

import { EnvSchema, loadPolicy } from "@hushmark/gateway";

import { hashSecret, SqlIdentityRepository } from "./admin/identity.js";
import { SqlAuditStore } from "./audit/store.js";
import { PostgresExecutor } from "./db/client.js";
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
const executor = new PostgresExecutor(databaseUrl);
const identity = new SqlIdentityRepository(executor);
await retryStartup(() => ensureBootstrapAdmin(identity), { attempts: 60, delayMs: 1_000 });

const publicKeyFile = process.env.HUSHMARK_LICENSE_PUBLIC_KEY_FILE;
const runtime = await buildEnterpriseServer({
  gateway: { config, policy: staticPolicy, logger: true },
  staticPolicy,
  signedLicense: JSON.parse(await readFile(licenseFile, "utf8")),
  identity,
  kms: createKms(),
  keyId,
  ...(publicKeyFile === undefined ? {} : { publicKeyPem: await readFile(publicKeyFile, "utf8") }),
  auditStore: new SqlAuditStore(executor),
  policyRepository: new SqlPolicyRepository(executor),
  vaultRepository: new SqlVaultRepository(executor),
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

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) throw new Error(`${name} is required`);
  return value;
}
