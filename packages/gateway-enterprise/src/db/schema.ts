import {
  bigint,
  boolean,
  customType,
  index,
  integer,
  jsonb,
  pgTable,
  primaryKey,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

import type { StaticPolicy } from "@hushmark/gateway";

import type { AuditEntity, AuditKind } from "../audit/types.js";
import type { AdminRole } from "../admin/rbac.js";

const bytea = customType<{ data: Uint8Array; driverData: Buffer }>({
  dataType() {
    return "bytea";
  },
  toDriver(value) {
    return Buffer.from(value);
  },
  fromDriver(value) {
    return new Uint8Array(value);
  },
});

export const roles = pgTable("roles", {
  name: text("name").$type<AdminRole>().primaryKey(),
});

export const users = pgTable(
  "users",
  {
    id: uuid("id").primaryKey(),
    email: text("email").notNull(),
    passwordHash: text("password_hash").notNull(),
    role: text("role")
      .$type<AdminRole>()
      .notNull()
      .references(() => roles.name),
    enabled: boolean("enabled").notNull().default(true),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [uniqueIndex("users_email_uq").on(table.email)],
);

export const apiKeys = pgTable(
  "api_keys",
  {
    id: uuid("id").primaryKey(),
    name: text("name").notNull(),
    prefix: text("prefix").notNull(),
    secretHash: text("secret_hash").notNull(),
    revokedAt: timestamp("revoked_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [uniqueIndex("api_keys_prefix_uq").on(table.prefix)],
);

export const adminSessions = pgTable(
  "admin_sessions",
  {
    tokenHash: text("token_hash").primaryKey(),
    userId: uuid("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  },
  (table) => [index("admin_sessions_expiry_idx").on(table.expiresAt)],
);

export const policies = pgTable(
  "policies",
  {
    id: uuid("id").primaryKey(),
    name: text("name").notNull(),
    priority: integer("priority").notNull(),
    apiKeyIds: jsonb("api_key_ids").$type<string[]>().notNull().default([]),
    allowedRoles: jsonb("allowed_roles").$type<AdminRole[]>().notNull().default([]),
    document: jsonb("document").$type<StaticPolicy>().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [index("policies_priority_idx").on(table.priority)],
);

export const auditEvents = pgTable("audit_events", {
  seq: bigint("seq", { mode: "number" }).primaryKey(),
  ts: timestamp("ts", { withTimezone: true }).notNull(),
  kind: text("kind").$type<AuditKind>().notNull(),
  actor: text("actor").notNull(),
  sessionId: text("session_id"),
  requestSha256: text("request_sha256").notNull(),
  entities: jsonb("entities").$type<AuditEntity[]>().notNull().default([]),
  prevHash: text("prev_hash").notNull(),
  hash: text("hash").notNull(),
});

export const vaultRecords = pgTable(
  "vault_records",
  {
    tenantId: text("tenant_id").notNull(),
    sessionId: text("session_id").notNull(),
    placeholder: text("placeholder").notNull(),
    ciphertext: bytea("ciphertext").notNull(),
    iv: bytea("iv").notNull(),
    tag: bytea("tag").notNull(),
    wrappedKey: text("wrapped_key").notNull(),
    entityType: text("entity_type").notNull(),
    valueHmac: text("value_hmac").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.tenantId, table.sessionId, table.placeholder] }),
    uniqueIndex("vault_records_value_hmac_uq").on(
      table.tenantId,
      table.sessionId,
      table.entityType,
      table.valueHmac,
    ),
    index("vault_records_expiry_idx").on(table.expiresAt),
  ],
);

export const vaultSessionKeys = pgTable(
  "vault_session_keys",
  {
    tenantId: text("tenant_id").notNull(),
    sessionId: text("session_id").notNull(),
    wrappedKey: text("wrapped_key").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [primaryKey({ columns: [table.tenantId, table.sessionId] })],
);

export const vaultPlaceholderCounters = pgTable(
  "vault_placeholder_counters",
  {
    tenantId: text("tenant_id").notNull(),
    sessionId: text("session_id").notNull(),
    label: text("label").notNull(),
    suffix: text("suffix").notNull(),
    nextValue: integer("next_value").notNull(),
  },
  (table) => [
    primaryKey({ columns: [table.tenantId, table.sessionId, table.label, table.suffix] }),
  ],
);

export const providers = pgTable("providers", {
  id: uuid("id").primaryKey(),
  name: text("name").notNull(),
  kind: text("kind").$type<"openai" | "anthropic">().notNull(),
  baseUrl: text("base_url").notNull(),
  auth: text("auth").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
