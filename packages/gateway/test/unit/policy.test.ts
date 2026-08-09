import { expect, it } from "vitest";

import { StaticPolicyEvaluator } from "../../src/policy/static.js";
import { testPolicy } from "../helpers.js";

it("evaluates type-specific rules before broader class rules", () => {
  const policy = testPolicy({
    rules: [
      { match: { kvkk_class: "general" }, action: "block" },
      { match: { types: ["PERSON"] }, action: "mask" },
    ],
  });
  expect(new StaticPolicyEvaluator(policy).evaluate("PERSON")).toBe("mask");
});
