import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import { assertNoLeak, extractPublicTree } from "../extract-public.js";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const temporaryDirectories: string[] = [];

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((path) => rm(path, { recursive: true })));
});

describe("public mirror extraction", () => {
  it("copies only the self-contained open-core allowlist with no corpus leak", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "hushmark-public-test-"));
    temporaryDirectories.push(temporary);
    const output = join(temporary, "public-mirror");
    await extractPublicTree({ repoRoot: REPO_ROOT, output });
    await assertNoLeak(output);

    const topLevel = new Set(await readdir(output));
    expect(topLevel).toEqual(
      new Set([
        ".dependency-cruiser.cjs",
        ".dependency-cruiser.fixture.cjs",
        ".editorconfig",
        ".github",
        ".gitignore",
        ".nvmrc",
        ".prettierignore",
        ".prettierrc.json",
        ".python-version",
        "CITATION.cff",
        "CHANGELOG.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "GOVERNANCE.md",
        "LICENSE",
        "MAINTAINERS.md",
        "NOTICE",
        "ORIGIN_AND_ATTRIBUTION.md",
        "README.md",
        "README.tr.md",
        "ROADMAP.md",
        "SECURITY.md",
        "SUPPORT.md",
        "THIRD_PARTY_NOTICES.md",
        "TRADEMARKS.md",
        "bench",
        "core",
        "docs",
        "eslint.config.mjs",
        "package.json",
        "packages",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "pyproject.toml",
        "renovate.json",
        "scripts",
        "sdk-py",
        "taxonomy",
        "tools",
        "tsconfig.base.json",
        "turbo.json",
        "uv.lock",
      ]),
    );
    expect(await readFile(join(output, "LICENSE"), "utf8")).toContain("Apache License");
    expect(await readFile(join(output, ".github/workflows/ci.yml"), "utf8")).toContain(
      "./scripts/verify.sh",
    );
    expect(await readFile(join(output, ".github/workflows/release.yml"), "utf8")).toContain(
      "npm publish dist/npm/hushmark-shared-0.1.1.tgz",
    );
    expect(await readFile(join(output, ".github/workflows/release.yml"), "utf8")).not.toContain(
      "workflow_dispatch",
    );
    const supplyChain = await readFile(join(output, ".github/workflows/supply-chain.yml"), "utf8");
    expect(supplyChain).toContain("open-core.spdx.json");
    expect(supplyChain).toContain("uv export --all-packages --no-dev --frozen --no-emit-workspace");
    expect(supplyChain).toContain("--no-deps --disable-pip --requirement");
    expect(supplyChain).toContain('tarfile.open(tarball, "r:gz")');
    expect(await readFile(join(output, "pnpm-workspace.yaml"), "utf8")).toContain(
      '"esbuild@>=0.27.3 <0.28.1": 0.28.2',
    );
    const publicLock = await readFile(join(output, "pnpm-lock.yaml"), "utf8");
    expect(publicLock).not.toMatch(
      /gateway-enterprise|apps\/console|license-issuer|tools\/release/u,
    );
    await expect(
      readFile(join(output, "bench/train/outputs/smoke-verdict.json")),
    ).rejects.toThrow();
  }, 15_000);
});
