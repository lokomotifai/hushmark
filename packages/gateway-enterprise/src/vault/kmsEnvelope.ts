import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

import { GatewayError, type PlaceholderVault, type VaultRecord } from "@hushmark/gateway";
import { TAXONOMY, type EntityType } from "@hushmark/shared";

import { sha256 } from "../audit/canonical.js";
import type { AuditWriter } from "../audit/writer.js";
import type { Kms } from "../kms/types.js";
import { requireRole, type AdminRole } from "../admin/rbac.js";
import type { EncryptedVaultRecord, VaultRepository } from "./repository.js";

const PLACEHOLDER_PARTS = /^\[([A-Z]{2,12})_[1-9][0-9]{0,4}\](#[0-9a-f]{4})?$/u;

export class KmsEnvelopeVault implements PlaceholderVault {
  readonly #dataKeys = new Map<string, { key: Uint8Array; wrapped: string }>();

  constructor(
    private readonly repository: VaultRepository,
    private readonly kms: Kms,
    private readonly keyId: string,
    private readonly audit: AuditWriter,
    private readonly now: () => number = Date.now,
  ) {}

  async put(session: string, placeholder: string, record: VaultRecord): Promise<void> {
    await this.intern(session, placeholder, record);
  }

  async intern(session: string, requested: string, record: VaultRecord): Promise<string> {
    const records = await this.repository.listSession(session);
    for (const existing of records) {
      if (existing.expiresAt.getTime() <= this.now() || existing.entityType !== record.type)
        continue;
      const value = await this.decrypt(existing);
      if (value.normalize("NFC") === record.value.normalize("NFC")) return existing.placeholder;
    }
    const placeholder = availablePlaceholder(requested, record.type, records);
    const dataKey = await this.sessionKey(session, records[0]);
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", dataKey.key, iv);
    cipher.setAAD(aad(session, placeholder, record.type));
    const ciphertext = Buffer.concat([cipher.update(record.value, "utf8"), cipher.final()]);
    await this.repository.put({
      sessionId: session,
      placeholder,
      ciphertext,
      iv,
      tag: cipher.getAuthTag(),
      wrappedKey: dataKey.wrapped,
      entityType: record.type,
      expiresAt: new Date(this.now() + record.ttlSec * 1_000),
    });
    return placeholder;
  }

  resolve(session: string, placeholder: string): Promise<string | null> {
    return this.resolveWithActor(session, placeholder, "system:gateway");
  }

  async resolveAs(
    role: AdminRole,
    actor: string,
    session: string,
    placeholder: string,
  ): Promise<string | null> {
    requireRole(role, ["admin", "operator"]);
    return this.resolveWithActor(session, placeholder, actor);
  }

  sweep(now: Date): Promise<number> {
    return this.repository.deleteExpired(now);
  }

  private async resolveWithActor(
    session: string,
    placeholder: string,
    actor: string,
  ): Promise<string | null> {
    const record = await this.repository.get(session, placeholder);
    if (record === null || record.expiresAt.getTime() <= this.now()) {
      await this.audit.append({
        kind: "UNRESOLVED_PLACEHOLDER",
        actor,
        session_id: session,
        request_sha256: sha256(placeholder),
        entities: [],
      });
      return null;
    }
    const value = await this.decrypt(record);
    await this.audit.append({
      kind: "VAULT_RESOLVE",
      actor,
      session_id: session,
      request_sha256: sha256(placeholder),
      entities: [{ type: record.entityType, action: "mask", count: 1 }],
    });
    return value;
  }

  private async decrypt(record: EncryptedVaultRecord): Promise<string> {
    try {
      const dataKey = await this.sessionKey(record.sessionId, record);
      const decipher = createDecipheriv("aes-256-gcm", dataKey.key, record.iv);
      decipher.setAAD(aad(record.sessionId, record.placeholder, record.entityType));
      decipher.setAuthTag(record.tag);
      return Buffer.concat([decipher.update(record.ciphertext), decipher.final()]).toString("utf8");
    } catch (error) {
      if (error instanceof GatewayError) throw error;
      throw new GatewayError("HM-5040", "vault unavailable");
    }
  }

  private async sessionKey(
    session: string,
    existing: EncryptedVaultRecord | undefined,
  ): Promise<{ key: Uint8Array; wrapped: string }> {
    const cached = this.#dataKeys.get(session);
    if (cached !== undefined) return cached;
    const value =
      existing === undefined
        ? await this.createDataKey()
        : {
            key: await this.kms.unwrap(this.keyId, existing.wrappedKey),
            wrapped: existing.wrappedKey,
          };
    if (value.key.byteLength !== 32) throw new GatewayError("HM-5040", "vault unavailable");
    this.#dataKeys.set(session, value);
    return value;
  }

  private async createDataKey(): Promise<{ key: Uint8Array; wrapped: string }> {
    const key = randomBytes(32);
    return { key, wrapped: await this.kms.wrap(this.keyId, key) };
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

function aad(session: string, placeholder: string, type: EntityType): Buffer {
  return Buffer.from(`${session}\0${placeholder}\0${type}`);
}
