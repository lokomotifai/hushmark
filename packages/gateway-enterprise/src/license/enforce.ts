import { GatewayError } from "@hushmark/gateway";

import { sha256 } from "../audit/canonical.js";
import type { AuditWriter, Clock } from "../audit/writer.js";
import { systemClock } from "../audit/writer.js";
import type { LicenseFeature, SignedLicense } from "./schema.js";
import { licenseState, type LicenseState } from "./state.js";
import { verifyLicense } from "./verify.js";

export class LicenseGuard {
  #license: SignedLicense | null = null;
  #reportedState: LicenseState | undefined;

  constructor(
    private readonly publicKeyPem: string,
    private readonly clock: Clock = systemClock,
    private readonly audit?: AuditWriter,
  ) {}

  async load(input: unknown): Promise<boolean> {
    this.#license = verifyLicense(input, this.publicKeyPem);
    this.#reportedState = undefined;
    await this.status();
    return this.#license !== null;
  }

  async status(): Promise<LicenseState> {
    const state = licenseState(this.#license, this.clock.now());
    if (state !== this.#reportedState) {
      this.#reportedState = state;
      await this.audit?.append({
        kind: "LICENSE_CHANGED",
        actor: "system:license",
        session_id: null,
        request_sha256: sha256(state),
        entities: [],
      });
    }
    return state;
  }

  async assertMutationAllowed(): Promise<void> {
    if ((await this.status()) === "frozen") {
      throw new GatewayError("HM-4301", "license frozen; configuration is read-only");
    }
  }

  has(feature: LicenseFeature): boolean {
    return this.#license?.entitlements.features.includes(feature) ?? false;
  }

  get license(): SignedLicense | null {
    return this.#license === null ? null : structuredClone(this.#license);
  }
}
