import { randomUUID } from "node:crypto";

import type {
  FastifyInstance,
  FastifyReply,
  FastifyRequest,
  HookHandlerDoneFunction,
} from "fastify";
import { GatewayError } from "@hushmark/gateway";
import { z } from "zod";

import { sha256 } from "../audit/canonical.js";
import type { AuditStore } from "../audit/store.js";
import type { AuditWriter } from "../audit/writer.js";
import { auditNdjson, verifyAuditChain } from "../audit/verify.js";
import type { LicenseGuard } from "../license/enforce.js";
import { EnterprisePolicySchema, type CachedPolicyEvaluator } from "../policy/db.js";
import { buildTedbirReportData, renderTedbirPdf } from "../reports/tedbir.js";
import type { KmsEnvelopeVault } from "../vault/kmsEnvelope.js";
import {
  issueApiKey,
  type IdentityRepository,
  type ProviderRecord,
  verifySecret,
} from "./identity.js";
import { requireRole } from "./rbac.js";
import { AdminSessions, type AdminPrincipal } from "./session.js";

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
  .object({ session_id: z.string().min(1), placeholder: z.string().min(1) })
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
  sessions?: AdminSessions;
  now?: () => Date;
}

export function registerAdminRoutes(
  app: FastifyInstance,
  dependencies: AdminRouteDependencies,
): void {
  const sessions = dependencies.sessions ?? new AdminSessions();
  const now = dependencies.now ?? (() => new Date());
  const principals = new WeakMap<FastifyRequest, AdminPrincipal>();

  const authenticate = (
    request: FastifyRequest,
    _reply: FastifyReply,
    done: HookHandlerDoneFunction,
  ): void => {
    try {
      const token = cookieValue(request.headers.cookie, "hm_admin");
      const principal = token === null ? null : sessions.resolve(token);
      if (principal === null) {
        done(new GatewayError("HM-4010", "missing or invalid admin session"));
        return;
      }
      principals.set(request, principal);
      done();
    } catch (error) {
      done(error instanceof Error ? error : new Error("admin authentication failed"));
    }
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

  app.post("/admin/auth/login", async (request, reply) => {
    const input = LoginSchema.parse(request.body);
    const user = await dependencies.identity.findUserByEmail(input.email);
    if (
      user === null ||
      !user.enabled ||
      !(await verifySecret(user.passwordHash, input.password))
    ) {
      await dependencies.audit.append({
        kind: "LOGIN_FAILED",
        actor: "anonymous",
        session_id: null,
        request_sha256: sha256("login-failed"),
        entities: [],
      });
      throw new GatewayError("HM-4010", "invalid email or password");
    }
    const token = sessions.create({ userId: user.id, role: user.role });
    reply.header(
      "set-cookie",
      `hm_admin=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800`,
    );
    await dependencies.audit.append({
      kind: "LOGIN_OK",
      actor: `user:${user.id}`,
      session_id: null,
      request_sha256: sha256(user.id),
      entities: [],
    });
    return { user: { id: user.id, email: user.email, role: user.role } };
  });

  app.post("/admin/auth/logout", { preHandler: authenticate }, (request, reply) => {
    const token = cookieValue(request.headers.cookie, "hm_admin");
    if (token !== null) sessions.revoke(token);
    reply.header("set-cookie", "hm_admin=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0");
    return { status: "ok" };
  });

  app.get("/admin/policies", { preHandler: authenticate }, () => dependencies.policies.list());
  app.post("/admin/policies", { preHandler: authenticate }, async (request) => {
    const principal = await mutationGuard(request);
    const policy = EnterprisePolicySchema.parse(request.body);
    await dependencies.policies.upsert(policy);
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, policy.id);
    return policy;
  });
  app.put("/admin/policies/:id", { preHandler: authenticate }, async (request) => {
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
  app.delete("/admin/policies/:id", { preHandler: authenticate }, async (request, reply) => {
    const principal = await mutationGuard(request);
    const id = idParam(request);
    const deleted = await dependencies.policies.delete(id);
    if (!deleted)
      return reply.status(404).send({ error: { code: "HM-4001", message: "not found" } });
    await auditAdminChange(dependencies.audit, "POLICY_CHANGED", principal, id);
    return { status: "deleted" };
  });

  app.get("/admin/api-keys", { preHandler: authenticate }, (request) => {
    requireRole(principalFor(request).role, ["admin"]);
    return dependencies.identity.listApiKeys();
  });
  app.post("/admin/api-keys", { preHandler: authenticate }, async (request) => {
    const principal = await mutationGuard(request);
    const issued = await issueApiKey(ApiKeySchema.parse(request.body).name, now());
    await dependencies.identity.putApiKey(issued.summary, issued.secretHash);
    await auditAdminChange(dependencies.audit, "KEY_CREATED", principal, issued.summary.id);
    return { ...issued.summary, secret: issued.secret };
  });
  app.delete("/admin/api-keys/:id", { preHandler: authenticate }, async (request) => {
    const principal = await mutationGuard(request);
    const id = idParam(request);
    const revoked = await dependencies.identity.revokeApiKey(id, now().toISOString());
    if (!revoked) throw new GatewayError("HM-4001", "api key not found or already revoked");
    await auditAdminChange(dependencies.audit, "KEY_REVOKED", principal, id);
    return { status: "revoked" };
  });

  app.get("/admin/providers", { preHandler: authenticate }, () =>
    dependencies.identity.listProviders(),
  );
  app.post("/admin/providers", { preHandler: authenticate }, async (request) => {
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

  app.get("/admin/audit/events", { preHandler: authenticate }, async (request) => {
    requireRole(principalFor(request).role, ["admin", "auditor"]);
    const query = AuditPageSchema.parse(request.query);
    const events = [...(await dependencies.auditStore.list())].reverse();
    const start = (query.page - 1) * query.limit;
    return {
      events: events.slice(start, start + query.limit),
      page: query.page,
      limit: query.limit,
      total: events.length,
    };
  });
  app.get("/admin/audit/export", { preHandler: authenticate }, async (request, reply) => {
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
  app.get("/admin/audit/verify", { preHandler: authenticate }, async (request) => {
    requireRole(principalFor(request).role, ["admin", "auditor"]);
    const range = AuditRangeSchema.parse(request.query);
    return verifyAuditChain(
      await dependencies.auditStore.list(),
      range.from ?? 1,
      range.to ?? "latest",
    );
  });

  app.post("/admin/vault/resolve", { preHandler: authenticate }, async (request) => {
    const principal = principalFor(request);
    const input = VaultResolveSchema.parse(request.body);
    const value = await dependencies.vault.resolveAs(
      principal.role,
      `user:${principal.userId}`,
      input.session_id,
      input.placeholder,
    );
    return { value };
  });

  app.get("/admin/license", { preHandler: authenticate }, async () => ({
    state: await dependencies.license.status(),
    license: dependencies.license.license,
  }));
  app.put("/admin/license", { preHandler: authenticate }, async (request) => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin"]);
    const valid = await dependencies.license.load(request.body);
    if (!valid) throw new GatewayError("HM-4001", "invalid license file");
    return { state: await dependencies.license.status() };
  });

  app.get("/admin/metrics/summary", { preHandler: authenticate }, async () => {
    const events = await dependencies.auditStore.list();
    const entityCounts: Record<string, number> = {};
    let masked = 0;
    let blocked = 0;
    for (const event of events) {
      if (event.kind === "MASK_APPLIED") masked += 1;
      if (event.kind === "REQUEST_BLOCKED") blocked += 1;
      event.entities.forEach((entity) => {
        entityCounts[entity.type] = (entityCounts[entity.type] ?? 0) + entity.count;
      });
    }
    return { masked, blocked, entity_counts: entityCounts };
  });

  app.get("/admin/reports/tedbir", { preHandler: authenticate }, async (request, reply) => {
    const principal = principalFor(request);
    requireRole(principal.role, ["admin", "auditor"]);
    if (!dependencies.license.has("tedbir_report")) {
      throw new GatewayError("HM-4030", "license does not include the report feature");
    }
    const query = ReportQuerySchema.parse(request.query);
    await auditAdminChange(dependencies.audit, "EXPORT_RUN", principal, "tedbir-report");
    const data = buildTedbirReportData(
      await dependencies.auditStore.list(),
      query.from,
      query.to,
      now().toISOString(),
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
    request_sha256: sha256(resourceId),
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
