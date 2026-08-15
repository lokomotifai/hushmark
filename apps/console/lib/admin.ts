import { ENTITY_TYPES, TAXONOMY, type EntityType } from "@hushmark/shared";
import { z } from "zod";

export type PolicyAction = "allow" | "mask" | "block";

export interface MetricsSummary {
  masked: number;
  blocked: number;
  entity_counts: Record<string, number>;
}

export interface EnterprisePolicy {
  id: string;
  name: string;
  priority: number;
  match: { api_key_ids?: string[]; roles?: ("admin" | "operator" | "auditor")[] };
  document: {
    version: 1;
    defaults: {
      unknown_entity: "block" | "mask";
      multimodal: "block";
      collision_mode: "reject" | "prefix";
      response_scan: "off" | "buffered";
    };
    rules: { match: { types: EntityType[] }; action: PolicyAction }[];
  };
}

export interface ProviderRecord {
  id: string;
  name: string;
  kind: "openai" | "anthropic";
  baseUrl: string;
  auth: string;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  revokedAt: string | null;
  createdAt: string;
  secret?: string;
}

export interface AuditRecord {
  seq: number;
  ts: string;
  kind: string;
  actor: string;
  session_id: string | null;
  entities: { type: string; action: string; count: number }[];
  hash: string;
}

export interface AuditPage {
  events: AuditRecord[];
  page: number;
  limit: number;
  total: number;
}

export interface LicenseStatus {
  state: "open" | "valid" | "expiring" | "grace" | "frozen";
  license: null | {
    licensee: string;
    tier: string;
    expires_at: string;
  };
}

export const PolicyInputSchema = z
  .object({
    name: z.string().min(1).max(120),
    priority: z.number().int(),
    match: z.object({}).strict(),
    document: z
      .object({
        version: z.literal(1),
        defaults: z
          .object({
            unknown_entity: z.enum(["block", "mask"]),
            multimodal: z.literal("block"),
            collision_mode: z.enum(["reject", "prefix"]),
            response_scan: z.enum(["off", "buffered"]),
          })
          .strict(),
        rules: z
          .array(
            z
              .object({
                match: z.object({ types: z.array(z.enum(ENTITY_TYPES)).length(1) }).strict(),
                action: z.enum(["allow", "mask", "block"]),
              })
              .strict(),
          )
          .length(ENTITY_TYPES.length),
      })
      .strict(),
  })
  .strict();

export type PolicyInput = z.infer<typeof PolicyInputSchema>;

export const matrixRows = ENTITY_TYPES.map((type) => ({ type, ...TAXONOMY[type] }));

export async function adminJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  const response = await fetch(`/api/admin/${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (response.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login");
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `HTTP ${String(response.status)}`);
  }
  return (await response.json()) as T;
}

export async function adminDownload(path: string, filename: string): Promise<void> {
  const response = await fetch(`/api/admin/${path}`, { method: "POST", cache: "no-store" });
  if (response.status === 401) {
    window.location.assign("/login");
    throw new Error("unauthorized");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { message?: string };
    } | null;
    throw new Error(payload?.error?.message ?? `HTTP ${String(response.status)}`);
  }
  const url = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function policyActions(
  policy: EnterprisePolicy | undefined,
): Record<EntityType, PolicyAction> {
  const actions = Object.fromEntries(
    matrixRows.map((row) => [row.type, row.default_action]),
  ) as Record<EntityType, PolicyAction>;
  for (const rule of policy?.document.rules ?? []) {
    for (const type of rule.match.types) actions[type] = rule.action;
  }
  return actions;
}

export function makePolicyInput(
  name: string,
  priority: number,
  actions: Record<EntityType, PolicyAction>,
): PolicyInput {
  return PolicyInputSchema.parse({
    name,
    priority,
    match: {},
    document: {
      version: 1,
      defaults: {
        unknown_entity: "block",
        multimodal: "block",
        collision_mode: "reject",
        response_scan: "off",
      },
      rules: matrixRows.map((row) => ({
        match: { types: [row.type] },
        action: actions[row.type],
      })),
    },
  });
}
