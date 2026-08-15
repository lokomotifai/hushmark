import { randomUUID } from "node:crypto";

import type { FastifyInstance, FastifyRequest } from "fastify";
import { GatewayError, MemoryRateLimiter, type RateLimiter } from "@hushmark/gateway";
import { z } from "zod";

import type { AuditStore } from "../audit/store.js";
import type { AuditWriter } from "../audit/writer.js";
import { auditNdjson } from "../audit/verify.js";
import type { LicenseGuard } from "../license/enforce.js";
import { EnterprisePolicySchema, type CachedPolicyEvaluator } from "../policy/db.js";
import { buildTedbirReportData, renderTedbirPdf } from "../reports/tedbir.js";
import type { KmsEnvelopeVault } from "../vault/kmsEnvelope.js";
import {
  issueApiKey,
  hashSecret,
  type AdminUser,
  type IdentityRepository,
  type ProviderRecord,
  verifySecret,
} from "./identity.js";
import { requireRole } from "./rbac.js";
import { AdminSessions, type AdminPrincipal, type AdminSessionStore } from "./session.js";

const LoginSchema = z.object({ email: z.email(), password: z.string().min(1).max(1_024) }).strict();
const ApiKeySchema = z.object({ name: z.string().min(1).max(120) }).strict();
const ProviderSchema = z
  .object({
    id: z.uuid().optional(),
    name: z.string().min(1).max(120),
    kind: z.enum(["openai", "anthropic"]),
    base_url: z.url(),
    auth: z.string().regex(/^(passthrough|env:[A-Z][A-Z0-9_]*)$/u),
  })
  .strict();
const VaultResolveSchema = z
  .object({
    tenant_id: z.string().min(1),
    session_id: z.string().min(1),
    placeholder: z.string().min(1),
  })
  .strict();
const AuditPageSchema = z
  .object({
    page: z.coerce.number().int().positive().default(1),
    limit: z.coerce.number().int().min(1).max(100).default(25),
  })
  .strict();
const AuditRangeSchema = z
  .object({
    from: z.coerce.number().int().positive().optional(),
    to: z.union([z.coerce.number().int().positive(), z.literal("latest")]).optional(),
  })
  .strict();
const ReportQuerySchema = z
  .object({
    from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u),
    format: z.literal("pdf").default("pdf"),
  })
  .strict();

export interface AdminRouteDependencies {
  identity: IdentityRepository;
  policies: CachedPolicyEvaluator;
  auditStore: AuditStore;
  audit: AuditWriter;
  vault: KmsEnvelopeVault;
  license: LicenseGuard;
  sessions?: AdminSessionStore;
  now?: () => Date;
  rateLimiter?: RateLimiter;
  requestRateLimitMax?: number;
  secureCookies?: boolean;
}

export function registerAdminRoutes(
  app: FastifyInstance,
  dependencies: AdminRouteDependencies,
): void {
  const sessions = dependencies.sessions ?? new AdminSessions();
  const now = dependencies.now ?? (() => new Date());
  const principals = new WeakMap<FastifyRequest, AdminPrincipal>();
  const rateLimiter = dependencies.rateLimiter ?? new MemoryRateLimiter();
  const secureCookie = dependencies.secureCookies ?? true;
  const cookieSecurity = secureCookie ? "; Secure" : "";
  const dummyPasswordHash = hashSecret(randomUUID());
  const passwordWork = new ConcurrencyGate(4);

  const authenticate = async (request: FastifyRequest): Promise<void> => {
    const token = cookieValue(request.headers.cookie, "hm_admin");
    const principal = token === null ? null : await sessions.resolve(token);
    if (principal === null) {
      throw new GatewayError("HM-4010", "missing or invalid admin session");
    }
    principals.set(request, principal);
  };
  const principalFor = (request: FastifyRequest): AdminPrincipal => {
    const principal = principals.get(request);
    if (principal === undefined) throw new GatewayError("HM-4010", "missing admin session");
    return principal;
  };
  const mutationGuard = async (request: FastifyRequest): Promise<AdminPrincipal> => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin"]);
    await dependencies.license.assertMutationAllowed();
    return principal;
  };
  const adminRoute = {
    config: {
      hushmarkAuth: "admin" as const,
      rateLimit: { max: dependencies.requestRateLimitMax ?? 300, timeWindow: 60_000 },
    },
    preHandler: authenticate,
  };

  app.post(
    "/admin/auth/login",
    {
      config: {
        hushmarkAuth: "public" as const,
        rateLimit: { max: 30, timeWindow: 60_000 },
      },
    },
    async (request, reply) => {
      const input = LoginSchema.parse(request.body);
      const normalizedEmail = input.email.normalize("NFC").toLowerCase();
      const emailFingerprint = dependencies.audit.fingerprint(normalizedEmail);
      const ipFingerprint = dependencies.audit.fingerprint(request.ip);
      const globalKey = "admin-login-global";
      const ipKey = `admin-login-ip:${ipFingerprint}`;
      const accountKey = `admin-login-account:${emailFingerprint}`;
      const allowedGlobally = await rateLimiter.consume(globalKey, 60, 60_000);
      const allowedByIp = await rateLimiter.consume(ipKey, 30, 60_000);
      const allowedByAccount = await rateLimiter.consume(accountKey, 10, 15 * 60_000);
      if (!allowedGlobally || !allowedByIp || !allowedByAccount || !passwordWork.tryAcquire()) {
        await dependencies.audit.append({
          kind: "LOGIN_FAILED",
          actor: `anonymous:${emailFingerprint.slice(0, 16)}`,
          session_id: null,
          request_sha256: dependencies.audit.fingerprint(`${ipFingerprint}\0rate-limited`),
          entities: [],
        });
        throw new GatewayError("HM-4290", "admin login rate limit exceeded");
      }
      let user: AdminUser | null;
      let passwordMatches: boolean;
      try {
        user = await dependencies.identity.findUserByEmail(input.email);
        const passwordHash = user?.enabled === true ? user.passwordHash : await dummyPasswordHash;
        passwordMatches = await verifySecret(passwordHash, input.password);
      } finally {
        passwordWork.release();
      }
      if (user === null || !user.enabled || !passwordMatches) {
        await dependencies.audit.append({
          kind: "LOGIN_FAILED",
          actor: `anonymous:${emailFingerprint.slice(0, 16)}`,
          session_id: null,
          request_sha256: dependencies.audit.fingerprint(
            `${ipFingerprint}\0${dependencies.audit.fingerprint(
              request.headers["user-agent"] ?? "unknown",
            )}`,
          ),
          entities: [],
        });
        throw new GatewayError("HM-4010", "invalid email or password");
      }
      const token = await sessions.create({ userId: user.id, role: user.role });
      await rateLimiter.reset?.(accountKey);
      reply.header(
        "set-cookie",
        `hm_admin=${token}; Path=/; HttpOnly${cookieSecurity}; SameSite=Strict; Max-Age=28800`,
      );
      await dependencies.audit.append({
        kind: "LOGIN_OK",
        actor: `user:${user.id}`,
        session_id: null,
        request_sha256: dependencies.audit.fingerprint(user.id),
        entities: [],
      });
      return { user: { id: user.id, email: user.email, role: user.role } };
    },
  );

  app.post("/admin/auth/logout", adminRoute, async (request, reply) => {
    const token = cookieValue(request.headers.cookie, "hm_admin");
    if (token !== null) await sessions.revoke(token);
    reply.header(
      "set-cookie",
      `hm_admin=; Path=/; HttpOnly${cookieSecurity}; SameSite=Strict; Max-Age=0`,
    );
    return { status: "ok" };
  });

  app.get("/admin/policies", adminRoute, () => dependencies.policies.list());
  app.post("/admin/policies", adminRoute, async (request) => {
    const principal = await mutationGuard(request);
    const policy = EnterprisePolicySchema.parse(request.body);
    await dependencies.policies.upsert(policy);
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, policy.id);
    return policy;
  });
  app.put("/admin/policies/:id", adminRoute, async (request) => {
    const principal = await mutationGuard(request);
    const id = idParam(request);
    const policy = EnterprisePolicySchema.parse({
      ...(request.body as Record<string, unknown>),
      id,
    });
    await dependencies.policies.upsert(policy);
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, id);
    return policy;
  });
  app.delete("/admin/policies/:id", adminRoute, async (request, reply) => {
    const principal = await mutationGuard(request);
    const id = idParam(request);
    const deleted = await dependencies.policies.delete(id);
    if (!deleted)
      return reply.status(404).send({ error: { code: "HM-4001", message: "not found" } });
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, id);
    return { status: "deleted" };
  });

  app.get("/admin/api-keys", adminRoute, (request) => {
    requireRole(principalFor(request).role, ["admin"]);
    return dependencies.identity.listApiKeys();
  });
  app.post("/admin/api-keys", adminRoute, async (request) => {
    const principal = await mutationGuard(request);
    // Keep the audit identifier outside the object that carries the one-time secret. This makes
    // the security boundary explicit to both reviewers and static data-flow analysis.
    const apiKeyId = randomUUID();
    const issued = await issueApiKey(ApiKeySchema.parse(request.body).name, now(), apiKeyId);
    await dependencies.identity.putApiKey(issued.summary, issued.secretHash);
    await auditAdminChange(dependencies.audit, "KEY_CREATED", principal, apiKeyId);
    return { ...issued.summary, secret: issued.secret };
  });
  app.delete("/admin/api-keys/:id", adminRoute, async (request) => {
    const principal = await mutationGuard(request);
    const id = idParam(request);
    const revoked = await dependencies.identity.revokeApiKey(id, now().toISOString());
    if (!revoked) throw new GatewayError("HM-4001", "api key not found or already revoked");
    await auditAdminChange(dependencies.audit, "KEY_REVOKED", principal, id);
    return { status: "revoked" };
  });

  app.get("/admin/providers", adminRoute, () => dependencies.identity.listProviders());
  app.post("/admin/providers", adminRoute, async (request) => {
    const principal = await mutationGuard(request);
    const input = ProviderSchema.parse(request.body);
    const provider: ProviderRecord = {
      id: input.id ?? randomUUID(),
      name: input.name,
      kind: input.kind,
      baseUrl: input.base_url,
      auth: input.auth,
    };
    await dependencies.identity.putProvider(provider);
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, provider.id);
    return provider;
  });

  app.get("/admin/audit/events", adminRoute, async (request) => {
    requireRole(principalFor(request).role, ["admin", "auditor"]);
    const query = AuditPageSchema.parse(request.query);
    const start = (query.page - 1) * query.limit;
    const result = await dependencies.auditStore.page(start, query.limit);
    return {
      events: result.records,
      page: query.page,
      limit: query.limit,
      total: result.total,
    };
  });
  app.post("/admin/audit/export", adminRoute, async (request, reply) => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin", "auditor"]);
    const range = AuditRangeSchema.parse(request.query);
    await auditAdminChange(dependencies.audit, "EXPORT_RUN", principal, "audit-export");
    const records = (await dependencies.auditStore.list()).filter(
      (record) =>
        record.seq >= (range.from ?? 1) &&
        (range.to === undefined || range.to === "latest" || record.seq <= range.to),
    );
    reply.header("content-type", "application/x-ndjson; charset=utf-8");
    return auditNdjson(records);
  });
  app.get("/admin/audit/verify", adminRoute, async (request) => {
    requireRole(principalFor(request).role, ["admin", "auditor"]);
    const range = AuditRangeSchema.parse(request.query);
    return dependencies.audit.verify(
      await dependencies.auditStore.list(),
      range.from ?? 1,
      range.to ?? "latest",
    );
  });

  app.post("/admin/vault/resolve", adminRoute, async (request) => {
    const principal = principalFor(request);
    if (!(await rateLimiter.consume(`admin-vault:${principal.userId}`, 60, 60_000))) {
      await dependencies.audit.append({
        kind: "REQUEST_BLOCKED",
        actor: `user:${principal.userId}`,
        session_id: null,
        request_sha256: dependencies.audit.fingerprint("admin-vault-rate-limited"),
        entities: [],
      });
      throw new GatewayError("HM-4290", "vault resolution rate limit exceeded");
    }
    const input = VaultResolveSchema.parse(request.body);
    const value = await dependencies.vault.resolveAs(
      principal.role,
      `user:${principal.userId}`,
      { tenantId: input.tenant_id, sessionId: input.session_id },
      input.placeholder,
    );
    return { value };
  });

  app.get("/admin/license", adminRoute, async () => ({
    state: await dependencies.license.status(),
    license: dependencies.license.license,
  }));
  app.put("/admin/license", adminRoute, async (request) => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin"]);
    const valid = await dependencies.license.load(request.body);
    if (!valid) throw new GatewayError("HM-4001", "invalid license file");
    return { state: await dependencies.license.status() };
  });

  app.get("/admin/metrics/summary", adminRoute, async () => {
    const metrics = await dependencies.auditStore.metrics();
    return {
      masked: metrics.masked,
      blocked: metrics.blocked,
      entity_counts: metrics.entityCounts,
    };
  });

  app.post("/admin/reports/tedbir", adminRoute, async (request, reply) => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin", "auditor"]);
    if (!dependencies.license.has("tedbir_report")) {
      throw new GatewayError("HM-4030", "license does not include the report feature");
    }
    const query = ReportQuerySchema.parse(request.query);
    await auditAdminChange(dependencies.audit, "EXPORT_RUN", principal, "tedbir-report");
    const data = await buildTedbirReportData(
      await dependencies.auditStore.list(),
      query.from,
      query.to,
      now().toISOString(),
      (records, from, to) => dependencies.audit.verify(records, from, to),
    );
    const pdf = await renderTedbirPdf(data);
    reply.header("content-type", "application/pdf");
    reply.header(
      "content-disposition",
      `attachment; filename="hushmark-tedbir-${query.from}-${query.to}.pdf"`,
    );
    return reply.send(pdf);
  });
}

class ConcurrencyGate {
  #active = 0;

  constructor(private readonly limit: number) {}

  tryAcquire(): boolean {
    if (this.#active >= this.limit) return false;
    this.#active += 1;
    return true;
  }

  release(): void {
    if (this.#active <= 0) throw new Error("concurrency gate released without acquisition");
    this.#active -= 1;
  }
}

async function auditAdminChange(
  audit: AuditWriter,
  kind: "POLICY_CHANGED" | "KEY_CREATED" | "KEY_REVOKED" | "EXPORT_RUN",
  principal: AdminPrincipal,
  resourceId: string,
): Promise<void> {
  await audit.append({
    kind,
    actor: `user:${principal.userId}`,
    session_id: null,
    request_sha256: audit.fingerprint(resourceId),
    entities: [],
  });
}

function cookieValue(header: string | undefined, name: string): string | null {
  if (header === undefined) return null;
  for (const part of header.split(";")) {
    const [key, ...value] = part.trim().split("=");
    if (key === name) return value.join("=");
  }
  return null;
}

function idParam(request: FastifyRequest): string {
  const parsed = z.object({ id: z.uuid() }).parse(request.params);
  return parsed.id;
}
