import type { SignedLicense } from "./schema.js";

export type LicenseState = "open" | "valid" | "expiring" | "grace" | "frozen";

const EXPIRING_WINDOW_MS = 30 * 24 * 60 * 60 * 1_000;

export function licenseState(license: SignedLicense | null, now: Date): LicenseState {
  if (license === null) return "open";
  const expiresAt = new Date(license.expires_at).getTime();
  const current = now.getTime();
  if (current <= expiresAt) {
    return expiresAt - current < EXPIRING_WINDOW_MS ? "expiring" : "valid";
  }
  const graceEnds = expiresAt + license.grace_days * 24 * 60 * 60 * 1_000;
  return current <= graceEnds ? "grace" : "frozen";
}
