import { TAXONOMY, type EntityType } from "@hushmark/shared";

import type { PolicyAction, StaticPolicy } from "../config.js";

export class StaticPolicyEvaluator {
  constructor(readonly policy: StaticPolicy) {}

  evaluate(entityType: EntityType): PolicyAction {
    const metadata = TAXONOMY[entityType];
    for (const rule of this.policy.rules) {
      if (rule.match.types?.includes(entityType) === true) {
        return rule.action;
      }
    }
    for (const rule of this.policy.rules) {
      if (rule.match.kvkk_class === metadata.kvkk_class) {
        return rule.action;
      }
    }
    return this.policy.defaults.unknown_entity;
  }
}
