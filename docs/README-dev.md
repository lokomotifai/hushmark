# Developer setup

Hushmark is a two-language monorepo: a Python 3.12 detection core and benchmark, and a Node.js 22
gateway, console, and SDK workspace. Install those exact runtime families plus
[uv](https://docs.astral.sh/uv/) and the pnpm version declared in `packageManager` (`10.34.4`), then
bootstrap the locked workspaces:

```sh
./scripts/bootstrap.sh
```

Bootstrap installs both workspaces from their lockfiles, downloads the model revision pinned in
`core/models.yaml`, verifies every file against its SHA-256 digest, and checks the ONNX export.
Set `HUSHMARK_FETCH_MODELS=0` to skip the download; only model-backed tests need those weights.
Set `HUSHMARK_PNPM_STORE_DIR` to relocate the pnpm store.

Run the complete local release gate with:

```sh
./scripts/verify.sh
```

The gate formats, lints, type-checks, tests, and builds both stacks; verifies module boundaries with
dependency-cruiser and import-linter; proves that the generated taxonomy, cross-language types, and
`docs/api-reference.md` match their sources; checks product claim language; and proves that private
strategy material and corpora are excluded from container build contexts.

For a smaller loop while iterating:

```sh
pnpm lint          # pnpm typecheck / pnpm test / pnpm build
uv run pytest      # uv run mypy bench/src core/src sdk-py/src
uv run ruff check bench core sdk-py tools examples/python-batch scripts/*.py
```

Integration and deployment paths need Docker with Compose v2. `deploy/docker/compose.dev.yaml`
brings up the evaluation stack with a fake upstream; `scripts/e2e-kind.sh` runs the Helm chart
end to end in a kind cluster.

Further reading: [configuration reference](config.md), [API reference](api-reference.md),
[security model](security.md), [engine comparison](benchmark-comparison.md),
[architecture decisions](adr/), and [CONTRIBUTING.md](../CONTRIBUTING.md).
