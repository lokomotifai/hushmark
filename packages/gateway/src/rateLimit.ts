export interface RateLimiter {
  consume(key: string, limit: number, windowMs: number): Promise<boolean> | boolean;
}

interface WindowRecord {
  count: number;
  resetsAt: number;
}

export class MemoryRateLimiter implements RateLimiter {
  readonly #windows = new Map<string, WindowRecord>();

  constructor(private readonly now: () => number = Date.now) {}

  consume(key: string, limit: number, windowMs: number): boolean {
    const now = this.now();
    const current = this.#windows.get(key);
    if (current === undefined || current.resetsAt <= now) {
      this.#windows.set(key, { count: 1, resetsAt: now + windowMs });
      this.sweep(now);
      return true;
    }
    current.count += 1;
    return current.count <= limit;
  }

  private sweep(now: number): void {
    if (this.#windows.size < 10_000) return;
    for (const [key, value] of this.#windows) {
      if (value.resetsAt <= now) this.#windows.delete(key);
    }
  }
}
