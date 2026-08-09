# Developer setup

hushmark uses Node.js 22, pnpm 9, Python 3.12, and uv. Install those exact runtime families, then
bootstrap the locked workspaces:

```sh
./scripts/bootstrap.sh
```

Run the complete local release gate with:

```sh
./scripts/verify.sh
```

The gate formats, lints, type-checks, tests, builds, verifies module boundaries and generated
taxonomy files, checks product wording, and proves that private strategy material is excluded from
container build contexts.
