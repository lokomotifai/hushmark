import { chmod, copyFile, lstat, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

const VERSION = "0.1.1";
const execFileAsync = promisify(execFile);
const SKIP_NAMES = new Set([
  ".DS_Store",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  ".turbo",
  "__pycache__",
  "coverage",
  "dist",
  "node_modules",
]);
const ROOT_FILES = [
  ".dependency-cruiser.cjs",
  ".dependency-cruiser.fixture.cjs",
  ".editorconfig",
  ".gitignore",
  ".nvmrc",
  ".prettierignore",
  ".prettierrc.json",
  ".python-version",
  "CHANGELOG.md",
  "CODE_OF_CONDUCT.md",
  "GOVERNANCE.md",
  "MAINTAINERS.md",
  "NOTICE",
  "ORIGIN_AND_ATTRIBUTION.md",
  "THIRD_PARTY_NOTICES.md",
  "TRADEMARKS.md",
  ".github/CODEOWNERS",
  ".github/ISSUE_TEMPLATE/bug.yml",
  ".github/ISSUE_TEMPLATE/documentation.yml",
  ".github/ISSUE_TEMPLATE/feature.yml",
  ".github/ISSUE_TEMPLATE/question.yml",
  "eslint.config.mjs",
  "package.json",
  "pyproject.toml",
  "renovate.json",
  "tsconfig.base.json",
  "turbo.json",
  "uv.lock",
] as const;
const SOURCE_DIRECTORIES = [
  "bench",
  "core",
  "docs",
  "packages/gateway",
  "packages/sdk-ts",
  "packages/shared",
  "sdk-py",
  "taxonomy",
  "tools/boundary-fixtures",
  "tools/codegen",
] as const;
const SCRIPT_FILES = [
  "scripts/bootstrap-gpu.sh",
  "scripts/build-training-bundle.py",
  "scripts/check-dependency-fixture.mjs",
  "scripts/fetch-models.py",
  "scripts/verify-training-bundle.py",
] as const;

export interface ExtractOptions {
  repoRoot: string;
  output: string;
}

function normalizedRelative(root: string, path: string): string {
  return relative(root, path).split(sep).join("/");
}

function shouldSkip(relativePath: string, name: string): boolean {
  if (SKIP_NAMES.has(name)) return true;
  return relativePath === "bench/train/outputs" || relativePath.startsWith("bench/train/outputs/");
}

async function copyEntry(
  sourceRoot: string,
  outputRoot: string,
  relativePath: string,
): Promise<void> {
  const source = join(sourceRoot, relativePath);
  const target = join(outputRoot, relativePath);
  const metadata = await lstat(source);
  if (metadata.isSymbolicLink())
    throw new Error(`public extraction refuses symlink: ${relativePath}`);
  if (metadata.isFile()) {
    await mkdir(dirname(target), { recursive: true });
    await copyFile(source, target);
    await chmod(target, metadata.mode & 0o777);
    return;
  }
  if (!metadata.isDirectory()) throw new Error(`unsupported source entry: ${relativePath}`);
  await mkdir(target, { recursive: true });
  for (const entry of await readdir(source, { withFileTypes: true })) {
    const child = join(relativePath, entry.name);
    if (shouldSkip(child.split(sep).join("/"), entry.name)) continue;
    await copyEntry(sourceRoot, outputRoot, child);
  }
}

function publicWorkspace(): string {
  return `packages:\n  - "packages/gateway"\n  - "packages/sdk-ts"\n  - "packages/shared"\n\nonlyBuiltDependencies:\n  - esbuild\n\noverrides:\n  "esbuild@<=0.24.2": 0.25.12\n  "esbuild@>=0.27.3 <0.28.1": 0.28.2\n`;
}

function publicBootstrap(): string {
  return `#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"
command -v pnpm >/dev/null 2>&1 || { echo "pnpm is required" >&2; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 1; }
pnpm_args=(install --frozen-lockfile)
if [[ -n "\${HUSHMARK_PNPM_STORE_DIR:-}" ]]; then
  pnpm_args+=(--store-dir "$HUSHMARK_PNPM_STORE_DIR")
fi
pnpm "\${pnpm_args[@]}"
uv sync --frozen --all-packages
echo "Public bootstrap complete. Model weights are distributed separately."
`;
}

function publicVerify(): string {
  return `#!/usr/bin/env bash
set -euo pipefail
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
pnpm format:check
pnpm build
pnpm lint
pnpm typecheck
pnpm test
pnpm depcruise
pnpm depcruise:fixture
uv run ruff format --check bench core sdk-py tools
uv run ruff check bench core sdk-py tools
uv run mypy bench/src core/src sdk-py/src
pytest_args=()
model_weights=models/hushmark-tr/pytorch_model.bin
if [[ ! -f "$model_weights" ]]; then
  pytest_args+=(
    --deselect=core/tests/test_ner_backends.py::test_torch_backend_detects_turkish_person_from_offline_model
    --deselect=core/tests/test_ner_backends.py::test_torch_and_onnx_backends_have_span_parity_on_turkish_fixture
    --deselect=sdk-py/tests/test_integration.py::test_python_sdk_and_batch_example_against_real_local_stack
  )
  echo "Optional model-weight tests are not part of the source-only public mirror."
fi
uv run pytest "\${pytest_args[@]}"
uv run lint-imports
uv run python tools/codegen/generate.py --check
uv run python tools/codegen/claims_lint.py
for private_path in research briefs hushmark PLAN.md PLAN-BRIEF.md EXECUTABLE-PLAN-PROMPT.md; do
  if [[ -e "$private_path" ]]; then echo "forbidden private path: $private_path" >&2; exit 1; fi
done
canary='HUSHMARK-CORPUS-'
canary+='CANARY-7f3a9d'
if rg -l --fixed-strings --hidden --glob '!.git/**' --glob '!node_modules/**' -- "$canary" .; then
  echo "corpus canary found" >&2
  exit 1
fi
if rg -n --hidden --glob '!.git/**' --glob '!node_modules/**' --glob '!.venv/**' \
  '([T]ODO|[T]BD|\\.skip\\(|pytest\\.mark\\.skip)' .; then
  echo "placeholder or skipped-test marker found" >&2
  exit 1
fi
echo "Standalone public-mirror verification passed."
`;
}

function publicCiWorkflow(): string {
  return `name: open-core-ci

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  repository-safety:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - name: Install Gitleaks
        run: |
          curl -fsSLo gitleaks.tar.gz https://github.com/gitleaks/gitleaks/releases/download/v8.28.0/gitleaks_8.28.0_linux_x64.tar.gz
          curl -fsSLo gitleaks.checksums https://github.com/gitleaks/gitleaks/releases/download/v8.28.0/gitleaks_8.28.0_checksums.txt
          grep 'gitleaks_8.28.0_linux_x64.tar.gz' gitleaks.checksums \
            | sed 's#gitleaks_8.28.0_linux_x64.tar.gz#gitleaks.tar.gz#' \
            | sha256sum --check
          tar -xzf gitleaks.tar.gz gitleaks
          sudo install -m 0755 gitleaks /usr/local/bin/gitleaks
      - name: Scan committed changes for secrets
        env:
          GITLEAKS_BASE: \${{ github.event.pull_request.base.sha || github.event.before }}
          GITLEAKS_HEAD: \${{ github.event.pull_request.head.sha || github.sha }}
        run: |
          if [[ "$GITLEAKS_BASE" =~ ^0+$ ]] || ! git cat-file -e "\${GITLEAKS_BASE}^{commit}" 2>/dev/null; then
            gitleaks git --redact --no-banner --verbose --log-opts="$GITLEAKS_HEAD" .
          else
            gitleaks git --redact --no-banner --verbose --log-opts="\${GITLEAKS_BASE}..\${GITLEAKS_HEAD}" .
          fi

  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: pnpm/action-setup@0977fd99725f1db4007ccb2928dbb4e90d06cc86 # v6.0.10
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          python-version: "3.12"
      - run: ./scripts/bootstrap.sh
      - run: ./scripts/verify.sh
`;
}

function publicSupplyChainWorkflow(): string {
  return `name: supply-chain

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:

permissions:
  contents: read

jobs:
  packages:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: pnpm/action-setup@0977fd99725f1db4007ccb2928dbb4e90d06cc86 # v6.0.10
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          python-version: "3.12"
      - run: ./scripts/bootstrap.sh
      - run: pnpm audit --audit-level high
      - name: Audit locked Python dependencies
        run: |
          mkdir -p dist
          uv export --all-packages --no-dev --frozen --no-emit-workspace --format requirements-txt --output-file dist/requirements.txt
          uvx --from pip-audit==2.9.0 pip-audit --progress-spinner=off --no-deps --disable-pip --requirement dist/requirements.txt
      - name: Build and inspect release archives
        run: |
          mkdir -p dist/npm dist/python
          pnpm --filter @hushmark/shared build
          pnpm --filter @hushmark/ai-sdk build
          pnpm --dir packages/shared pack --pack-destination "$GITHUB_WORKSPACE/dist/npm"
          pnpm --dir packages/sdk-ts pack --pack-destination "$GITHUB_WORKSPACE/dist/npm"
          uv build --package hushmark-core --out-dir dist/python/core
          uv build --package hushmark-sdk --out-dir dist/python/sdk
          for archive in dist/npm/*.tgz dist/python/*/*.tar.gz; do tar -tzf "$archive"; done
          python - <<'PY'
          import tarfile
          from pathlib import Path, PurePosixPath
          from zipfile import ZipFile

          forbidden = {"research", "briefs", "hushmark", "PLAN.md", "PLAN-BRIEF.md", "EXECUTABLE-PLAN-PROMPT.md"}

          def leaked_paths(names: list[str]) -> list[str]:
              return [name for name in names if any(part in forbidden for part in PurePosixPath(name).parts)]

          for tarball in [*Path("dist/npm").glob("*.tgz"), *Path("dist/python").glob("*/*.tar.gz")]:
              with tarfile.open(tarball, "r:gz") as archive:
                  leaked = leaked_paths(archive.getnames())
                  if leaked:
                      raise SystemExit(f"forbidden paths in {tarball}: {leaked}")
          for wheel in Path("dist/python").glob("*/*.whl"):
              with ZipFile(wheel) as archive:
                  leaked = leaked_paths(archive.namelist())
                  if leaked:
                      raise SystemExit(f"forbidden paths in {wheel}: {leaked}")
          PY
      - name: Install Syft and Grype
        run: |
          curl -fsSLO https://github.com/anchore/syft/releases/download/v1.50.0/syft_1.50.0_linux_amd64.tar.gz
          curl -fsSLO https://github.com/anchore/syft/releases/download/v1.50.0/syft_1.50.0_checksums.txt
          grep 'syft_1.50.0_linux_amd64.tar.gz' syft_1.50.0_checksums.txt | sha256sum --check
          tar -xzf syft_1.50.0_linux_amd64.tar.gz syft
          sudo install -m 0755 syft /usr/local/bin/syft
          curl -fsSLO https://github.com/anchore/grype/releases/download/v0.116.1/grype_0.116.1_linux_amd64.tar.gz
          curl -fsSLO https://github.com/anchore/grype/releases/download/v0.116.1/grype_0.116.1_checksums.txt
          grep 'grype_0.116.1_linux_amd64.tar.gz' grype_0.116.1_checksums.txt | sha256sum --check
          tar -xzf grype_0.116.1_linux_amd64.tar.gz grype
          sudo install -m 0755 grype /usr/local/bin/grype
      - name: Generate SBOM and enforce fixed-critical budget
        run: |
          syft dir:. -o cyclonedx-json=open-core.cdx.json -o spdx-json=open-core.spdx.json
          grype sbom:open-core.spdx.json --only-fixed --fail-on critical
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: open-core-release-evidence
          path: |
            dist
            open-core.cdx.json
            open-core.spdx.json
`;
}

function publicReleaseWorkflow(): string {
  return `name: release

on:
  push:
    tags: ["v[0-9]*.[0-9]*.[0-9]*"]

permissions:
  contents: read

concurrency:
  group: release-\${{ github.ref }}
  cancel-in-progress: false

jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
      - name: Validate immutable release source
        env:
          RELEASE_TAG: \${{ github.ref_name }}
        run: |
          test "$RELEASE_TAG" = "v${VERSION}"
          git fetch --no-tags origin main
          git merge-base --is-ancestor "$GITHUB_SHA" origin/main
      - uses: pnpm/action-setup@0977fd99725f1db4007ccb2928dbb4e90d06cc86 # v6.0.10
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          python-version: "3.12"
      - run: ./scripts/bootstrap.sh
      - run: ./scripts/verify.sh

  npm:
    needs: verify
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: npm
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: pnpm/action-setup@0977fd99725f1db4007ccb2928dbb4e90d06cc86 # v6.0.10
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
          registry-url: https://registry.npmjs.org
      - run: npm install --global npm@11.5.1
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter @hushmark/shared build && pnpm --filter @hushmark/ai-sdk build
      - name: Pack and inspect public npm packages
        run: |
          mkdir -p dist/npm
          pnpm --dir packages/shared pack --pack-destination "$GITHUB_WORKSPACE/dist/npm"
          pnpm --dir packages/sdk-ts pack --pack-destination "$GITHUB_WORKSPACE/dist/npm"
          tar -tzf dist/npm/hushmark-shared-${VERSION}.tgz
          tar -tzf dist/npm/hushmark-ai-sdk-${VERSION}.tgz
      - name: Publish with npm trusted publishing
        run: |
          npm publish dist/npm/hushmark-shared-${VERSION}.tgz --access public --provenance
          npm publish dist/npm/hushmark-ai-sdk-${VERSION}.tgz --access public --provenance

  pypi-core:
    needs: verify
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: pypi-core
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          python-version: "3.12"
      - run: uv build --package hushmark-core --out-dir dist/core
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1
        with:
          packages-dir: dist/core

  pypi-sdk:
    needs: verify
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: pypi-sdk
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: astral-sh/setup-uv@20cfd1bf945f4377ade1205e4dbc17946fc9a30d # v10.0.1
        with:
          python-version: "3.12"
      - run: uv build --package hushmark-sdk --out-dir dist/sdk
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1
        with:
          packages-dir: dist/sdk
`;
}

async function writeGeneratedFiles(repoRoot: string, output: string): Promise<void> {
  const packageJson = JSON.parse(await readFile(join(repoRoot, "package.json"), "utf8")) as Record<
    string,
    unknown
  >;
  packageJson.name = "hushmark-open-core";
  packageJson.version = VERSION;
  await writeFile(join(output, "package.json"), `${JSON.stringify(packageJson, null, 2)}\n`);
  await writeFile(join(output, "pnpm-workspace.yaml"), publicWorkspace());
  await writeFile(join(output, "LICENSE"), await readFile(join(repoRoot, "LICENSE"), "utf8"));
  await mkdir(join(output, "scripts"), { recursive: true });
  await writeFile(join(output, "scripts/bootstrap.sh"), publicBootstrap(), { mode: 0o755 });
  await writeFile(join(output, "scripts/verify.sh"), publicVerify(), { mode: 0o755 });
  await mkdir(join(output, ".github/workflows"), { recursive: true });
  await writeFile(join(output, ".github/workflows/ci.yml"), publicCiWorkflow());
  await writeFile(join(output, ".github/workflows/supply-chain.yml"), publicSupplyChainWorkflow());
  await writeFile(join(output, ".github/workflows/release.yml"), publicReleaseWorkflow());
}

async function validatePublicLockfile(repoRoot: string, output: string): Promise<void> {
  const pnpmCli = join(repoRoot, "node_modules", "pnpm", "bin", "pnpm.cjs");
  await execFileAsync(
    process.execPath,
    [pnpmCli, "install", "--lockfile-only", "--offline", "--frozen-lockfile", "--ignore-scripts"],
    {
      cwd: output,
      env: { ...process.env, CI: "true" },
    },
  );
}

async function listFiles(root: string, path = root): Promise<string[]> {
  const result: string[] = [];
  for (const entry of await readdir(path, { withFileTypes: true })) {
    const absolute = join(path, entry.name);
    if (entry.isDirectory()) result.push(...(await listFiles(root, absolute)));
    else if (entry.isFile()) result.push(normalizedRelative(root, absolute));
  }
  return result;
}

export async function assertNoLeak(output: string): Promise<void> {
  const forbiddenSegments = new Set(["briefs", "hushmark", "research"]);
  const forbiddenFiles = new Set(["EXECUTABLE-PLAN-PROMPT.md", "PLAN-BRIEF.md", "PLAN.md"]);
  const canary = "HUSHMARK-CORPUS-" + "CANARY-7f3a9d";
  for (const path of await listFiles(output)) {
    const segments = path.split("/");
    if (segments.some((segment) => forbiddenSegments.has(segment)) || forbiddenFiles.has(path)) {
      throw new Error(`private path leaked into public tree: ${path}`);
    }
    if ((await readFile(join(output, path), "utf8")).includes(canary)) {
      throw new Error(`corpus canary leaked into public tree: ${path}`);
    }
  }
}

export async function extractPublicTree(options: ExtractOptions): Promise<void> {
  const repoRoot = resolve(options.repoRoot);
  const output = resolve(options.output);
  await rm(output, { recursive: true, force: true });
  await mkdir(output, { recursive: true });
  for (const path of ROOT_FILES) await copyEntry(repoRoot, output, path);
  for (const path of SOURCE_DIRECTORIES) await copyEntry(repoRoot, output, path);
  for (const path of SCRIPT_FILES) await copyEntry(repoRoot, output, path);
  const publicRoot = join(repoRoot, "tools/release/public-root");
  for (const entry of await readdir(publicRoot)) await copyEntry(publicRoot, output, entry);
  await writeGeneratedFiles(repoRoot, output);
  await validatePublicLockfile(repoRoot, output);
  await assertNoLeak(output);
  console.log(`public mirror extracted to ${output}`);
}

const invokedPath = process.argv[1];
if (invokedPath !== undefined && import.meta.url === pathToFileURL(resolve(invokedPath)).href) {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  await extractPublicTree({ repoRoot, output: resolve(repoRoot, "dist/public-mirror") });
}
