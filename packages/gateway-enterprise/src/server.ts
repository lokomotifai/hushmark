import type { FastifyInstance } from "fastify";
import { buildServer, type ServerDependencies, type StaticPolicy } from "@hushmark/gateway";

import { registerAdminRoutes } from "./admin/routes.js";
import type { AdminSessions } from "./admin/session.js";
import type { IdentityRepository } from "./admin/identity.js";
import { MemoryAuditStore, type AuditStore } from "./audit/store.js";
import { AuditWriter, type Clock, systemClock } from "./audit/writer.js";
import type { Kms } from "./kms/types.js";
import { LicenseGuard } from "./license/enforce.js";
import { EMBEDDED_LICENSE_PUBLIC_KEY } from "./license/verify.js";
import {
  CachedPolicyEvaluator,
  MemoryPolicyRepository,
  type PolicyRepository,
} from "./policy/db.js";
import { KmsEnvelopeVault } from "./vault/kmsEnvelope.js";
import { MemoryVaultRepository, type VaultRepository } from "./vault/repository.js";
import { startVaultSweeper } from "./vault/sweeper.js";

export interface EnterpriseServerDependencies {
  gateway: Omit<ServerDependencies, "vault" | "onMaskEvent">;
  staticPolicy: StaticPolicy;
  signedLicense: unknown;
  identity: IdentityRepository;
  kms: Kms;
  keyId: string;
  publicKeyPem?: string;
  auditStore?: AuditStore;
  policyRepository?: PolicyRepository;
  vaultRepository?: VaultRepository;
  sessions?: AdminSessions;
  clock?: Clock;
  nowMs?: () => number;
}

export interface EnterpriseRuntime {
  app: FastifyInstance;
  enterprise: boolean;
  auditStore: AuditStore;
  audit: AuditWriter;
  license: LicenseGuard;
  vault?: KmsEnvelopeVault;
  policies?: CachedPolicyEvaluator;
}

export async function buildEnterpriseServer(
  dependencies: EnterpriseServerDependencies,
): Promise<EnterpriseRuntime> {
  const auditStore = dependencies.auditStore ?? new MemoryAuditStore();
  const audit = new AuditWriter(auditStore, dependencies.clock ?? systemClock);
  const license = new LicenseGuard(
    dependencies.publicKeyPem ?? EMBEDDED_LICENSE_PUBLIC_KEY,
    dependencies.clock ?? systemClock,
    audit,
  );
  if (!(await license.load(dependencies.signedLicense))) {
    return {
      app: buildServer(dependencies.gateway),
      enterprise: false,
      auditStore,
      audit,
      license,
    };
  }

  const vault = new KmsEnvelopeVault(
    dependencies.vaultRepository ?? new MemoryVaultRepository(),
    dependencies.kms,
    dependencies.keyId,
    audit,
    dependencies.nowMs,
  );
  const policies = new CachedPolicyEvaluator(
    dependencies.policyRepository ?? new MemoryPolicyRepository(),
    dependencies.staticPolicy,
  );
  const app = buildServer({
    ...dependencies.gateway,
    vault,
    onMaskEvent: (event) => audit.appendMaskEvent(event).then(() => undefined),
  });
  registerAdminRoutes(app, {
    identity: dependencies.identity,
    policies,
    auditStore,
    audit,
    vault,
    license,
    ...(dependencies.sessions === undefined ? {} : { sessions: dependencies.sessions }),
    ...(dependencies.clock === undefined
      ? {}
      : { now: () => dependencies.clock?.now() ?? new Date() }),
  });
  const stopSweeper = startVaultSweeper(vault);
  app.addHook("onClose", () => stopSweeper());
  return { app, enterprise: true, auditStore, audit, license, vault, policies };
}
