import { ENTITY_TYPES } from "@hushmark/shared";
import { expect, it } from "vitest";

import { makePolicyInput, policyActions } from "../lib/admin";

it("validates a closed policy matrix covering every taxonomy type", () => {
  const policy = makePolicyInput("Regulated", 100, policyActions(undefined));
  expect(policy.document.rules).toHaveLength(ENTITY_TYPES.length);
  expect(policy.document.rules.map((rule) => rule.match.types[0])).toEqual(ENTITY_TYPES);
});
