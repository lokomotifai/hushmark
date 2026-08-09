import {
  EntityTypeSchema,
  type EntityType,
  type MaskRequest,
  type MaskResponse,
} from "@hushmark/shared";

import type { StaticPolicy } from "../config.js";
import type { CorePort } from "../coreClient.js";
import { GatewayError } from "../errors.js";
import { StaticPolicyEvaluator } from "../policy/static.js";
import type { PlaceholderVault } from "../vault/memory.js";

export interface TextSegment {
  id: string;
  text: string;
  set(value: string): void;
}

export interface MaskEvent {
  event: "MASK_APPLIED";
  session_id: string;
  entities: { type: EntityType; action: "allow" | "mask"; count: number }[];
}

export class MaskPipeline {
  readonly #policy: StaticPolicyEvaluator;

  constructor(
    private readonly core: CorePort,
    policy: StaticPolicy,
    private readonly vault: PlaceholderVault,
    private readonly ttlSec: number,
    private readonly onEvent: (event: MaskEvent) => Promise<void> | void = () => undefined,
  ) {
    this.#policy = new StaticPolicyEvaluator(policy);
  }

  async apply(segments: TextSegment[], session: string): Promise<MaskResponse> {
    const request: MaskRequest = {
      items: segments.map(({ id, text }) => ({ id, text })),
      language: "tr",
      session,
      include_values: true,
      collision_mode: this.#policy.policy.defaults.collision_mode,
    };
    const response = await this.core.mask(request);
    const segmentsById = new Map(segments.map((segment) => [segment.id, segment]));
    const blocked = new Set<EntityType>();
    const counts = new Map<string, { type: EntityType; action: "allow" | "mask"; count: number }>();

    for (const item of response.items) {
      const segment = segmentsById.get(item.id);
      if (segment === undefined) {
        throw new GatewayError("HM-5030", "invalid detection engine response");
      }
      let maskedText = item.masked_text;
      for (const mapping of item.mappings) {
        const parsedType = EntityTypeSchema.safeParse(mapping.type);
        if (!parsedType.success) {
          throw new GatewayError("HM-4201", "blocked entity types", ["UNKNOWN"]);
        }
        if (mapping.value === undefined) {
          throw new GatewayError("HM-5030", "detection engine omitted mapping values");
        }
        const action = this.#policy.evaluate(parsedType.data);
        if (action === "block") {
          blocked.add(mapping.type);
          continue;
        }
        if (action === "allow") {
          maskedText = replaceAllLiteral(maskedText, mapping.placeholder, mapping.value);
        } else {
          const canonical = await this.vault.intern(session, mapping.placeholder, {
            type: mapping.type,
            value: mapping.value,
            ttlSec: this.ttlSec,
          });
          maskedText = replaceAllLiteral(maskedText, mapping.placeholder, canonical);
        }
        const key = `${mapping.type}\0${action}`;
        const current = counts.get(key);
        counts.set(key, {
          type: mapping.type,
          action,
          count: (current?.count ?? 0) + 1,
        });
      }
      segment.set(maskedText);
    }
    if (blocked.size > 0) {
      throw new GatewayError("HM-4201", "blocked entity types", [...blocked].sort());
    }
    await this.onEvent({
      event: "MASK_APPLIED",
      session_id: session,
      entities: [...counts.values()],
    });
    return response;
  }
}

function replaceAllLiteral(text: string, needle: string, replacement: string): string {
  return text.split(needle).join(replacement);
}
