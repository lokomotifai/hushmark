import { EntityTypeSchema } from "@hushmark/shared";
import { z } from "zod";

export const AUDIT_KINDS = [
  "MASK_APPLIED",
  "REQUEST_BLOCKED",
  "UNRESOLVED_PLACEHOLDER",
  "VAULT_RESOLVE",
  "POLICY_CHANGED",
  "KEY_CREATED",
  "KEY_REVOKED",
  "LICENSE_CHANGED",
  "LOGIN_OK",
  "LOGIN_FAILED",
  "EXPORT_RUN",
  "ANCHOR",
] as const;

export type AuditKind = (typeof AUDIT_KINDS)[number];

export const AuditEntitySchema = z
  .object({
    type: EntityTypeSchema,
    action: z.enum(["allow", "mask", "redact", "block"]),
    count: z.number().int().positive(),
  })
  .strict();

export type AuditEntity = z.infer<typeof AuditEntitySchema>;

export const AuditInputSchema = z
  .object({
    ts: z.iso.datetime({ offset: true }),
    kind: z.enum(AUDIT_KINDS),
    actor: z.string().min(1).max(160),
    session_id: z.string().min(1).max(160).nullable(),
    request_sha256: z.string().regex(/^[0-9a-f]{64}$/u),
    entities: z.array(AuditEntitySchema),
  })
  .strict();

export type AuditInput = z.infer<typeof AuditInputSchema>;

export const AuditRecordSchema = AuditInputSchema.extend({
  seq: z.number().int().positive(),
  prev_hash: z.string().regex(/^[0-9a-f]{64}$/u),
  hash: z.string().regex(/^[0-9a-f]{64}$/u),
}).strict();

export type AuditRecord = z.infer<typeof AuditRecordSchema>;
