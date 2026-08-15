import { randomUUID } from "node:crypto";

import {
  PolicySchema,
  StaticPolicyEvaluator,
  type PolicyAction,
  type StaticPolicy,
} from "@hushmark/gateway";
import type { EntityType } from "@hushmark/shared";
import { z } from "zod";

import { AdminRoleSchema, type AdminRole } from "../admin/rbac.js";
import type { SqlExecutor } from "../db/client.js";

export const EnterprisePolicySchema = z
  .object({
    id: z.uuid().default(() => randomUUID()),
    name: z.string().min(1).max(120),
    priority: z.number().int(),
    match: z
      .object({
        api_key_ids: z.array(z.uuid()).optional(),
        roles: z.array(AdminRoleSchema).optional(),
      })
      .strict()
      .default({}),
    document: PolicySchema,
  })
  .strict();

export type EnterprisePolicy = z.infer<typeof EnterprisePolicySchema>;

export interface PolicyContext {
  apiKeyId?: string;
  role?: AdminRole;
}

export interface PolicyRepository {
  list(): Promise<EnterprisePolicy[]>;
  upsert(policy: EnterprisePolicy): Promise<void>;
  delete(id: string): Promise<boolean>;
}

export class SqlPolicyRepository implements PolicyRepository {
  constructor(private readonly sql: SqlExecutor) {}

  async list(): Promise<EnterprisePolicy[]> {
    const result = await this.sql.query<{
      id: string;
      name: string;
      priority: number;
      api_key_ids: unknown;
      allowed_roles: unknown;
      document: unknown;
    }>(
      "SELECT id, name, priority, api_key_ids, allowed_roles, document FROM policies ORDER BY priority DESC, id ASC",
    );
    return result.rows.map((row) =>
      EnterprisePolicySchema.parse({
        id: row.id,
        name: row.name,
        priority: row.priority,
        match: { api_key_ids: row.api_key_ids, roles: row.allowed_roles },
        document: row.document,
      }),
    );
  }

  async upsert(policy: EnterprisePolicy): Promise<void> {
    const parsed = EnterprisePolicySchema.parse(policy);
    await this.sql.query(
      `INSERT INTO policies (id, name, priority, api_key_ids, allowed_roles, document, updated_at)
       VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, now())
       ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, priority = EXCLUDED.priority,
       api_key_ids = EXCLUDED.api_key_ids, allowed_roles = EXCLUDED.allowed_roles,
       document = EXCLUDED.document, updated_at = now()`,
      [
        parsed.id,
        parsed.name,
        parsed.priority,
        JSON.stringify(parsed.match.api_key_ids ?? []),
        JSON.stringify(parsed.match.roles ?? []),
        JSON.stringify(parsed.document),
      ],
    );
  }

  async delete(id: string): Promise<boolean> {
    const result = await this.sql.query("DELETE FROM policies WHERE id = $1", [id]);
    return (result.rowCount ?? 0) > 0;
  }
}

export class MemoryPolicyRepository implements PolicyRepository {
  readonly #policies = new Map<string, EnterprisePolicy>();

  list(): Promise<EnterprisePolicy[]> {
    return Promise.resolve(
      [...this.#policies.values()]
        .map((policy) => structuredClone(policy))
        .sort((left, right) => right.priority - left.priority || left.id.localeCompare(right.id)),
    );
  }

  upsert(policy: EnterprisePolicy): Promise<void> {
    const parsed = EnterprisePolicySchema.parse(policy);
    this.#policies.set(parsed.id, structuredClone(parsed));
    return Promise.resolve();
  }

  delete(id: string): Promise<boolean> {
    return Promise.resolve(this.#policies.delete(id));
  }
}

export class CachedPolicyEvaluator {
  #cache: EnterprisePolicy[] | undefined;

  constructor(
    private readonly repository: PolicyRepository,
    private readonly fallback: StaticPolicy,
  ) {}

  async select(context: PolicyContext): Promise<EnterprisePolicy | null> {
    const policies = this.#cache ?? (this.#cache = await this.repository.list());
    const matches = policies.filter((policy) => matchesContext(policy, context));
    matches.sort(
      (left, right) =>
        right.priority - left.priority ||
        specificity(right) - specificity(left) ||
        left.id.localeCompare(right.id),
    );
    return matches[0] ?? null;
  }

  async list(): Promise<EnterprisePolicy[]> {
    return structuredClone(this.#cache ?? (this.#cache = await this.repository.list()));
  }

  async evaluate(type: EntityType, context: PolicyContext): Promise<PolicyAction> {
    const selected = await this.select(context);
    return new StaticPolicyEvaluator(selected?.document ?? this.fallback).evaluate(type);
  }

  async resolve(context: PolicyContext): Promise<StaticPolicy> {
    const selected = await this.select(context);
    return structuredClone(selected?.document ?? this.fallback);
  }

  async upsert(policy: EnterprisePolicy): Promise<void> {
    await this.repository.upsert(EnterprisePolicySchema.parse(policy));
    this.invalidate();
  }

  async delete(id: string): Promise<boolean> {
    const deleted = await this.repository.delete(id);
    this.invalidate();
    return deleted;
  }

  invalidate(): void {
    this.#cache = undefined;
  }
}

function matchesContext(policy: EnterprisePolicy, context: PolicyContext): boolean {
  const apiKeys = policy.match.api_key_ids;
  const roles = policy.match.roles;
  if (
    apiKeys !== undefined &&
    (context.apiKeyId === undefined || !apiKeys.includes(context.apiKeyId))
  ) {
    return false;
  }
  if (roles !== undefined && (context.role === undefined || !roles.includes(context.role))) {
    return false;
  }
  return true;
}

function specificity(policy: EnterprisePolicy): number {
  return Number(policy.match.api_key_ids !== undefined) + Number(policy.match.roles !== undefined);
}
