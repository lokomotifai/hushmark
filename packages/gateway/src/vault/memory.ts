import { TAXONOMY, type EntityType } from "@hushmark/shared";

export interface VaultRecord {
  type: EntityType;
  value: string;
  ttlSec: number;
}

export interface VaultScope {
  tenantId: string;
  sessionId: string;
}

export interface VaultStore {
  put(scope: VaultScope, placeholder: string, record: VaultRecord): Promise<void>;
  resolve(scope: VaultScope, placeholder: string): Promise<string | null>;
  sweep(now: Date): Promise<number>;
}

export interface PlaceholderVault extends VaultStore {
  intern(scope: VaultScope, requested: string, record: VaultRecord): Promise<string>;
}

interface StoredRecord extends VaultRecord {
  expiresAt: number;
  reverseKey: string;
}

export type VaultEvent =
  | { event: "VAULT_EVICTED"; type: EntityType }
  | { event: "UNRESOLVED_PLACEHOLDER"; placeholder: string };

const PLACEHOLDER_PARTS = /^\[([A-Z]{2,12})_[1-9][0-9]{0,4}\](#[0-9a-f]{16})?$/u;

export class MemoryVault implements PlaceholderVault {
  readonly #entries = new Map<string, StoredRecord>();
  readonly #reverse = new Map<string, string>();
  readonly #counters = new Map<string, number>();

  constructor(
    private readonly maxEntries = 100_000,
    private readonly now: () => number = Date.now,
    private readonly onEvent: (event: VaultEvent) => void = () => undefined,
  ) {}

  put(scope: VaultScope, placeholder: string, record: VaultRecord): Promise<void> {
    return this.intern(scope, placeholder, record).then(() => undefined);
  }

  intern(scope: VaultScope, requested: string, record: VaultRecord): Promise<string> {
    const reverseKey = this.reverseKey(scope, record.type, record.value);
    const existing = this.#reverse.get(reverseKey);
    if (existing !== undefined) {
      const stored = this.#entries.get(this.entryKey(scope, existing));
      if (stored !== undefined && stored.expiresAt > this.now()) {
        this.touch(this.entryKey(scope, existing), stored);
        return Promise.resolve(existing);
      }
      this.#reverse.delete(reverseKey);
    }

    const placeholder = this.availablePlaceholder(scope, requested, record.type);
    const key = this.entryKey(scope, placeholder);
    const stored: StoredRecord = {
      ...record,
      expiresAt: this.now() + record.ttlSec * 1_000,
      reverseKey,
    };
    this.#entries.set(key, stored);
    this.#reverse.set(reverseKey, placeholder);
    this.evictToLimit();
    return Promise.resolve(placeholder);
  }

  resolve(scope: VaultScope, placeholder: string): Promise<string | null> {
    const key = this.entryKey(scope, placeholder);
    const stored = this.#entries.get(key);
    if (stored === undefined || stored.expiresAt <= this.now()) {
      if (stored !== undefined) this.deleteEntry(key, stored);
      this.onEvent({ event: "UNRESOLVED_PLACEHOLDER", placeholder });
      return Promise.resolve(null);
    }
    this.touch(key, stored);
    return Promise.resolve(stored.value);
  }

  sweep(now: Date): Promise<number> {
    let purged = 0;
    for (const [key, stored] of this.#entries) {
      if (stored.expiresAt <= now.getTime()) {
        this.deleteEntry(key, stored);
        purged += 1;
      }
    }
    return Promise.resolve(purged);
  }

  get size(): number {
    return this.#entries.size;
  }

  private availablePlaceholder(scope: VaultScope, requested: string, type: EntityType): string {
    const match = PLACEHOLDER_PARTS.exec(requested);
    const label = match?.[1] ?? TAXONOMY[type].tr_label;
    const suffix = match?.[2] ?? "";
    const counterKey = `${scopeKey(scope)}\0${label}${suffix}`;
    let index = this.#counters.get(counterKey) ?? 0;
    let candidate = requested;
    while (this.#entries.has(this.entryKey(scope, candidate))) {
      index += 1;
      candidate = `[${label}_${String(index)}]${suffix}`;
    }
    const candidateIndex = /^\[[A-Z]{2,12}_([1-9][0-9]{0,4})\]/u.exec(candidate)?.[1];
    this.#counters.set(counterKey, Math.max(index, Number(candidateIndex ?? 0)));
    return candidate;
  }

  private entryKey(scope: VaultScope, placeholder: string): string {
    return `${scopeKey(scope)}\0${placeholder}`;
  }

  private reverseKey(scope: VaultScope, type: EntityType, value: string): string {
    return `${scopeKey(scope)}\0${type}\0${value.normalize("NFC")}`;
  }

  private touch(key: string, stored: StoredRecord): void {
    this.#entries.delete(key);
    this.#entries.set(key, stored);
  }

  private deleteEntry(key: string, stored: StoredRecord): void {
    this.#entries.delete(key);
    this.#reverse.delete(stored.reverseKey);
  }

  private evictToLimit(): void {
    while (this.#entries.size > this.maxEntries) {
      const oldest = this.#entries.entries().next().value;
      if (oldest === undefined) return;
      this.deleteEntry(oldest[0], oldest[1]);
      this.onEvent({ event: "VAULT_EVICTED", type: oldest[1].type });
    }
  }
}

function scopeKey(scope: VaultScope): string {
  return `${scope.tenantId}\0${scope.sessionId}`;
}
