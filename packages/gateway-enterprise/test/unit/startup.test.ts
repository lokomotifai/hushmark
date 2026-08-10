import { describe, expect, it, vi } from "vitest";

import { retryStartup } from "../../src/startup.js";

describe("enterprise startup retry", () => {
  it("survives a transient dependency failure", async () => {
    const operation = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(new Error("database DNS is not ready"))
      .mockResolvedValue("ready");
    const sleep = vi.fn<(delayMs: number) => Promise<void>>().mockResolvedValue();

    await expect(retryStartup(operation, { attempts: 3, delayMs: 25, sleep })).resolves.toBe(
      "ready",
    );
    expect(operation).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(25);
  });

  it("preserves the terminal startup error", async () => {
    const terminal = new Error("database unavailable");
    const operation = vi.fn<() => Promise<void>>().mockRejectedValue(terminal);
    const sleep = vi.fn<(delayMs: number) => Promise<void>>().mockResolvedValue();

    await expect(retryStartup(operation, { attempts: 2, delayMs: 10, sleep })).rejects.toBe(
      terminal,
    );
    expect(operation).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledTimes(1);
  });
});
