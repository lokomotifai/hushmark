export interface RateLimiter {
  consume(key: string, limit: number, windowMs: number): Promise<boolean> | boolean;
  reset?(key: string): Promise<void> | void;
}

interface WindowRecord {
  count: number;
  resetsAt: number;
}

export class MemoryRateLimiter implements RateLimiter {
  readonly #windows = new Map<string, WindowRecord>();
  #newKeysSinceSweep = 0;

  constructor(
    private readonly now: () => number = Date.now,
    private readonly maxKeys = 20_000,
  ) {
    if (!Number.isSafeInteger(maxKeys) || maxKeys < 1) {
      throw new RangeError("rate limiter maxKeys must be a positive safe integer");
    }
  }

  consume(key: string, limit: number, windowMs: number): boolean {
    const now = this.now();
    const current = this.#windows.get(key);
    if (current === undefined || current.resetsAt <= now) {
      if (current === undefined) this.makeCapacity(now);
      this.#windows.set(key, { count: 1, resetsAt: now + windowMs });
      return true;
    }
    current.count += 1;
    return current.count <= limit;
  }

  reset(key: string): void {
    this.#windows.delete(key);
  }

  private makeCapacity(now: number): void {
    this.#newKeysSinceSweep += 1;
    if (this.#newKeysSinceSweep >= 256) {
      this.#newKeysSinceSweep = 0;
      this.sweepExpired(now);
    }
    while (this.#windows.size >= this.maxKeys) {
      const oldest = this.#windows.keys().next().value;
      if (oldest === undefined) break;
      this.#windows.delete(oldest);
    }
  }

  private sweepExpired(now: number): void {
    for (const [key, value] of this.#windows) {
      if (value.resetsAt <= now) this.#windows.delete(key);
    }
  }
}
