import { expect, it } from "vitest";

import { CachedPolicyEvaluator, MemoryPolicyRepository } from "../../src/policy/db.js";
import { testPolicy } from "../helpers.js";

it("selects the highest-priority matching enterprise policy and invalidates its cache", async () => {
  const repository = new MemoryPolicyRepository();
  const evaluator = new CachedPolicyEvaluator(repository, testPolicy());
  const id = "20000000-0000-4000-8000-000000000001";
  const document = {
    ...testPolicy(),
    rules: [{ match: { types: ["TR_TCKN" as const] }, action: "block" as const }],
  };
  await evaluator.upsert({
    id,
    name: "generic-high",
    priority: 100,
    match: {},
    document,
  });
  await evaluator.upsert({
    id: "20000000-0000-4000-8000-000000000002",
    name: "role-low",
    priority: 10,
    match: { roles: ["admin"] },
    document: testPolicy(),
  });

  expect(await evaluator.evaluate("TR_TCKN", { role: "admin" })).toBe("block");
  await evaluator.upsert({
    id,
    name: "generic-high",
    priority: 100,
    match: {},
    document: testPolicy(),
  });
  expect(await evaluator.evaluate("TR_TCKN", { role: "admin" })).toBe("mask");
});
