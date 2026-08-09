import { spawnSync } from "node:child_process";

const result = spawnSync(
  "pnpm",
  ["exec", "depcruise", "--config", ".dependency-cruiser.fixture.cjs", "tools/boundary-fixtures"],
  { encoding: "utf8" },
);

if (result.status === 0) {
  console.error("The forbidden dependency fixture unexpectedly passed.");
  process.exit(1);
}

if (!`${result.stdout}\n${result.stderr}`.includes("open-core-must-not-import-enterprise")) {
  console.error("The fixture failed for an unexpected reason.");
  console.error(result.stdout);
  console.error(result.stderr);
  process.exit(1);
}

console.log("Forbidden dependency fixture was rejected as expected.");
