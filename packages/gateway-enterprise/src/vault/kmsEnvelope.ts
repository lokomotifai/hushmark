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
    const dataKey = await this.writeSessionKey(scope, await this.repository.getSessionKey(scope));
    try {
      const valueHmac = hmacValue(dataKey.key, record.type, record.value);
      const duplicate = await this.repository.getByValueHmac(scope, record.type, valueHmac);
      if (duplicate !== null && duplicate.expiresAt.getTime() > this.now()) {
        return duplicate.placeholder;
      }
      const requestedParts = placeholderParts(requested, record.type);
      const placeholder = await this.repository.allocatePlaceholder(
        scope,
        requestedParts.label,
        requestedParts.suffix,
        requestedParts.minimum,
      );
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
    } finally {
      dataKey.key.fill(0);
    }
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
      const dataKey = await this.keyForWrapped(scope, record.wrappedKey);
      try {
        const decipher = createDecipheriv("aes-256-gcm", dataKey.key, record.iv);
        decipher.setAAD(aad(scope, record.placeholder, record.entityType));
        decipher.setAuthTag(record.tag);
        return Buffer.concat([decipher.update(record.ciphertext), decipher.final()]).toString(
          "utf8",
        );
      } finally {
        dataKey.key.fill(0);
      }
    } catch (error) {
      if (error instanceof GatewayError) throw error;
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }

  private async writeSessionKey(
    scope: VaultScope,
    existingWrapped: string | null,
  ): Promise<{ key: Uint8Array; wrapped: string }> {
    if (existingWrapped !== null) {
      return this.keyForWrapped(scope, existingWrapped);
    }
    const candidate = await this.createDataKey();
    const wrapped = await this.repository.claimSessionKey(scope, candidate.wrapped);
    if (wrapped === candidate.wrapped) {
      this.cacheKey(scope, wrapped, candidate.key);
      const key = new Uint8Array(candidate.key);
      candidate.key.fill(0);
      return { key, wrapped };
    }
    candidate.key.fill(0);
    return this.keyForWrapped(scope, wrapped);
  }

  private async keyForWrapped(
    scope: VaultScope,
    wrapped: string,
  ): Promise<{ key: Uint8Array; wrapped: string }> {
    this.evictExpiredKeys();
    const cacheKey = wrappedCacheKey(scope, wrapped);
    const cached = this.#dataKeys.get(cacheKey);
    if (cached !== undefined) {
      cached.lastUsed = this.now();
      return { key: new Uint8Array(cached.key), wrapped: cached.wrapped };
    }
    const key = await this.kms.unwrap(this.keyId, wrapped);
    if (key.byteLength !== 32) throw new GatewayError("HM-5040", "vault unavailable");
    this.cacheKey(scope, wrapped, key);
    const result = new Uint8Array(key);
    key.fill(0);
    return { key: result, wrapped };
  }

  private cacheKey(scope: VaultScope, wrapped: string, key: Uint8Array): void {
    this.#dataKeys.set(wrappedCacheKey(scope, wrapped), {
      key: new Uint8Array(key),
      wrapped,
      expiresAt: this.now() + this.keyCacheTtlMs,
      lastUsed: this.now(),
    });
    this.evictOverflowKeys();
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

function placeholderParts(
  requested: string,
  type: EntityType,
): { label: string; suffix: string; minimum: number } {
  const match = PLACEHOLDER_PARTS.exec(requested);
  const label = match?.[1] ?? TAXONOMY[type].tr_label;
  const suffix = match?.[2] ?? "";
  const counter = /^\[[A-Z]{2,12}_([1-9][0-9]{0,4})\]/u.exec(requested)?.[1];
  return { label, suffix, minimum: counter === undefined ? 1 : Number(counter) };
}

function aad(scope: VaultScope, placeholder: string, type: EntityType): Buffer {
  return Buffer.from(`${scope.tenantId}\0${scope.sessionId}\0${placeholder}\0${type}`);
}

function scopeKey(scope: VaultScope): string {
  return `${scope.tenantId}\0${scope.sessionId}`;
}

function wrappedCacheKey(scope: VaultScope, wrapped: string): string {
  return `${scopeKey(scope)}\0${wrapped}`;
}

function hmacValue(key: Uint8Array, type: EntityType, value: string): string {
  return createHmac("sha256", key)
    .update(`${type}\0${value.normalize("NFC")}`)
    .digest("hex");
}
