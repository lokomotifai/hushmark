import { createCipheriv, createDecipheriv, createHmac, randomBytes } from "node:crypto";

import {
  GatewayError,
  type PlaceholderVault,
  type VaultRecord,
  type VaultScope,
} from "@hushmark/gateway";
import { TAXONOMY, type EntityType } from "@hushmark/shared";

import { sha256 } from "../audit/canonical.js";
import type { AuditWriter } from "../audit/writer.js";
import type { Kms } from "../kms/types.js";
import { requireRole, type AdminRole } from "../admin/rbac.js";
import type { EncryptedVaultRecord, VaultRepository } from "./repository.js";

const PLACEHOLDER_PARTS = /^\[([A-Z]{2,12})_[1-9][0-9]{0,4}\](#[0-9a-f]{16})?$/u;

export class KmsEnvelopeVault implements PlaceholderVault {
  readonly #dataKeys = new Map<
    string,
    { key: Uint8Array; wrapped: string; expiresAt: number; lastUsed: number }
  >();

  constructor(
    private readonly repository: VaultRepository,
    private readonly kms: Kms,
    private readonly keyId: string,
    private readonly audit: AuditWriter,
    private readonly now: () => number = Date.now,
    private readonly maxCachedKeys = 10_000,
    private readonly keyCacheTtlMs = 5 * 60 * 1_000,
  ) {}

  async put(scope: VaultScope, placeholder: string, record: VaultRecord): Promise<void> {
    await this.intern(scope, placeholder, record);
  }

  async intern(scope: VaultScope, requested: string, record: VaultRecord): Promise<string> {
    const records = await this.repository.listSession(scope);
    const dataKey = await this.sessionKey(scope, records[0]);
    const valueHmac = hmacValue(dataKey.key, record.type, record.value);
    const duplicate = await this.repository.getByValueHmac(scope, record.type, valueHmac);
    if (duplicate !== null && duplicate.expiresAt.getTime() > this.now()) {
      return duplicate.placeholder;
    }
    const placeholder = availablePlaceholder(requested, record.type, records);
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", dataKey.key, iv);
    cipher.setAAD(aad(scope, placeholder, record.type));
    const ciphertext = Buffer.concat([cipher.update(record.value, "utf8"), cipher.final()]);
    await this.repository.put({
      tenantId: scope.tenantId,
      sessionId: scope.sessionId,
      placeholder,
      ciphertext,
      iv,
      tag: cipher.getAuthTag(),
      wrappedKey: dataKey.wrapped,
      entityType: record.type,
      valueHmac,
      expiresAt: new Date(this.now() + record.ttlSec * 1_000),
    });
    return placeholder;
  }

  resolve(scope: VaultScope, placeholder: string): Promise<string | null> {
    return this.resolveWithActor(scope, placeholder, `api-key:${scope.tenantId}`);
  }

  async resolveAs(
    role: AdminRole,
    actor: string,
    scope: VaultScope,
    placeholder: string,
  ): Promise<string | null> {
    requireRole(role, ["admin", "operator"]);
    return this.resolveWithActor(scope, placeholder, actor);
  }

  sweep(now: Date): Promise<number> {
    return this.repository.deleteExpired(now);
  }

  private async resolveWithActor(
    scope: VaultScope,
    placeholder: string,
    actor: string,
  ): Promise<string | null> {
    const record = await this.repository.get(scope, placeholder);
    if (record === null || record.expiresAt.getTime() <= this.now()) {
      await this.audit.append({
        kind: "UNRESOLVED_PLACEHOLDER",
        actor,
        session_id: scope.sessionId,
        request_sha256: sha256(placeholder),
        entities: [],
      });
      return null;
    }
    const value = await this.decrypt(record);
    await this.audit.append({
      kind: "VAULT_RESOLVE",
      actor,
      session_id: scope.sessionId,
      request_sha256: sha256(placeholder),
      entities: [{ type: record.entityType, action: "mask", count: 1 }],
    });
    return value;
  }

  private async decrypt(record: EncryptedVaultRecord): Promise<string> {
    try {
      const scope = { tenantId: record.tenantId, sessionId: record.sessionId };
      const dataKey = await this.sessionKey(scope, record);
      const decipher = createDecipheriv("aes-256-gcm", dataKey.key, record.iv);
      decipher.setAAD(aad(scope, record.placeholder, record.entityType));
      decipher.setAuthTag(record.tag);
      return Buffer.concat([decipher.update(record.ciphertext), decipher.final()]).toString("utf8");
    } catch (error) {
      if (error instanceof GatewayError) throw error;
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }

  private async sessionKey(
    scope: VaultScope,
    existing: EncryptedVaultRecord | undefined,
  ): Promise<{ key: Uint8Array; wrapped: string }> {
    this.evictExpiredKeys();
    const cacheKey = scopeKey(scope);
    const cached = this.#dataKeys.get(cacheKey);
    if (cached !== undefined) {
      cached.lastUsed = this.now();
      return cached;
    }
    const value =
      existing === undefined
        ? await this.createDataKey()
        : {
            key: await this.kms.unwrap(this.keyId, existing.wrappedKey),
            wrapped: existing.wrappedKey,
          };
    if (value.key.byteLength !== 32) throw new GatewayError("HM-5040", "vault unavailable");
    this.#dataKeys.set(cacheKey, {
      ...value,
      expiresAt: this.now() + this.keyCacheTtlMs,
      lastUsed: this.now(),
    });
    this.evictOverflowKeys();
    return value;
  }

  private async createDataKey(): Promise<{ key: Uint8Array; wrapped: string }> {
    const key = randomBytes(32);
    return { key, wrapped: await this.kms.wrap(this.keyId, key) };
  }

  private evictExpiredKeys(): void {
    const now = this.now();
    for (const [cacheKey, value] of this.#dataKeys) {
      if (value.expiresAt <= now) this.deleteCachedKey(cacheKey, value);
    }
  }

  private evictOverflowKeys(): void {
    while (this.#dataKeys.size > this.maxCachedKeys) {
      const oldest = [...this.#dataKeys.entries()].sort(
        ([, left], [, right]) => left.lastUsed - right.lastUsed,
      )[0];
      if (oldest === undefined) return;
      this.deleteCachedKey(oldest[0], oldest[1]);
    }
  }

  private deleteCachedKey(cacheKey: string, value: { key: Uint8Array; wrapped: string }): void {
    value.key.fill(0);
    this.#dataKeys.delete(cacheKey);
  }
}

function availablePlaceholder(
  requested: string,
  type: EntityType,
  records: readonly EncryptedVaultRecord[],
): string {
  const occupied = new Set(records.map((record) => record.placeholder));
  if (!occupied.has(requested)) return requested;
  const match = PLACEHOLDER_PARTS.exec(requested);
  const label = match?.[1] ?? TAXONOMY[type].tr_label;
  const suffix = match?.[2] ?? "";
  for (let index = 1; index <= 99_999; index += 1) {
    const candidate = `[${label}_${String(index)}]${suffix}`;
    if (!occupied.has(candidate)) return candidate;
  }
  throw new GatewayError("HM-5040", "vault unavailable");
}

function aad(scope: VaultScope, placeholder: string, type: EntityType): Buffer {
  return Buffer.from(`${scope.tenantId}\0${scope.sessionId}\0${placeholder}\0${type}`);
}

function scopeKey(scope: VaultScope): string {
  return `${scope.tenantId}\0${scope.sessionId}`;
}

function hmacValue(key: Uint8Array, type: EntityType, value: string): string {
  return createHmac("sha256", key)
    .update(`${type}\0${value.normalize("NFC")}`)
    .digest("hex");
}
