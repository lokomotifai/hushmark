import type { PlaceholderVault } from "@hushmark/gateway";

export function startVaultSweeper(
  vault: PlaceholderVault,
  intervalMs = 60_000,
  now: () => Date = () => new Date(),
): () => void {
  const timer = setInterval(() => void vault.sweep(now()), intervalMs);
  timer.unref();
  return () => clearInterval(timer);
}
