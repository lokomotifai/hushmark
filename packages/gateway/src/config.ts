import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { ENTITY_TYPES } from "@hushmark/shared";
import { parse as parseYaml } from "yaml";
import { z } from "zod";

const ApiKeySchema = z.string().regex(/^hm_k1_[A-Za-z0-9_-]{16,}$/u);

export const EnvSchema = z
  .object({
    HUSHMARK_GATEWAY_HOST: z.string().default("0.0.0.0"),
    HUSHMARK_GATEWAY_PORT: z.coerce.number().int().min(1).max(65_535).default(8080),
    HUSHMARK_API_KEYS: z
      .string()
      .transform((value) => value.split(",").map((key) => key.trim()))
      .pipe(z.array(ApiKeySchema).min(1)),
    HUSHMARK_CORE_URL: z.url().default("http://127.0.0.1:8000"),
    HUSHMARK_CORE_SERVICE_TOKEN: z.string().min(32).optional(),
    HUSHMARK_OPENAI_UPSTREAM: z.url(),
    HUSHMARK_ANTHROPIC_UPSTREAM: z.url(),
    HUSHMARK_OPENAI_API_KEY: z.string().min(1).optional(),
    HUSHMARK_ANTHROPIC_API_KEY: z.string().min(1).optional(),
    HUSHMARK_POLICY_PATH: z.string().default("packages/gateway/policy.yaml"),
    HUSHMARK_VAULT_MAX_ENTRIES: z.coerce.number().int().positive().default(100_000),
    HUSHMARK_VAULT_TTL_SEC: z.coerce.number().int().positive().default(86_400),
    HUSHMARK_UNMASK_LIMIT: z.coerce.number().int().positive().max(1_000).default(100),
    HUSHMARK_RATE_LIMIT_MAX: z.coerce.number().int().positive().default(120),
    HUSHMARK_RATE_LIMIT_WINDOW_SEC: z.coerce.number().int().positive().default(60),
    HUSHMARK_BODY_LIMIT_BYTES: z.coerce.number().int().positive().default(1_048_576),
    HUSHMARK_TRUST_PROXY: z
      .enum(["true", "false"])
      .default("false")
      .transform((value) => value === "true"),
  })
  .strict();

const ActionSchema = z.enum(["allow", "mask", "block"]);
const MatchSchema = z
  .object({
    types: z.array(z.enum(ENTITY_TYPES)).min(1).optional(),
    kvkk_class: z.enum(["general", "special", "secret"]).optional(),
  })
  .strict()
  .refine((value) => value.types !== undefined || value.kvkk_class !== undefined);

export const PolicySchema = z
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
            match: MatchSchema,
            action: ActionSchema,
          })
          .strict(),
      )
      .min(1),
  })
  .strict();

export type GatewayConfig = z.infer<typeof EnvSchema>;
export type StaticPolicy = z.infer<typeof PolicySchema>;
export type PolicyAction = z.infer<typeof ActionSchema>;

export function loadConfig(environment: NodeJS.ProcessEnv = process.env): GatewayConfig {
  const keys = new Set(Object.keys(EnvSchema.shape));
  const unknown = Object.keys(environment).filter(
    (key) => key.startsWith("HUSHMARK_") && !keys.has(key),
  );
  if (unknown.length > 0)
    throw new Error(`unknown gateway environment keys: ${unknown.sort().join(",")}`);
  return EnvSchema.parse(Object.fromEntries([...keys].map((key) => [key, environment[key]])));
}

export async function loadPolicy(path: string): Promise<StaticPolicy> {
  const content = await readFile(resolve(path), "utf8");
  return PolicySchema.parse(parseYaml(content));
}
