# Contributing to Hushmark

Thank you for helping improve Hushmark. Contributions may be code, tests, documentation, issue
triage, design review, or reproducible evaluation evidence.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md) and license your
contribution under [Apache-2.0](LICENSE).

## Before you start

- Search existing issues and pull requests.
- Open an issue before large, user-visible, security-sensitive, taxonomy, or API changes.
- Report vulnerabilities privately under [SECURITY.md](SECURITY.md).
- Never commit credentials, personal data, customer payloads, private corpora, or model weights.
- Keep synthetic fixtures clearly synthetic and safe to publish.

The full [`lokomotifai/hushmark`](https://github.com/lokomotifai/hushmark) repository is the canonical
development history. `hushmark-open-core` is produced from an explicit allowlist; core, gateway,
SDK, benchmark, and taxonomy code changes should therefore target this repository first.

## Development setup

Prerequisites are Node.js 22, pnpm 9, Python 3.12, uv, and Docker for integration paths.

```bash
git clone https://github.com/lokomotifai/hushmark.git
cd hushmark
./scripts/bootstrap.sh
./scripts/verify.sh
```

Model-backed tests require the separately distributed, checksum-verified `hushmark-tr` artifact.
The standard source verification does not download or regenerate production weights implicitly.

Useful focused commands:

```bash
pnpm lint
pnpm typecheck
pnpm test
uv run pytest
```

Generated taxonomy and clients must be changed through their source definitions and generators.
Run the full verification script before requesting review.

## Pull requests

Keep each pull request focused and explain:

1. the user or operator problem;
2. the chosen behavior and alternatives considered;
3. tests or evidence added;
4. compatibility, privacy, and security impact;
5. documentation or migration work required.

Maintainers may ask for a smaller change, additional evidence, or an ADR for difficult-to-reverse
decisions. Passing CI is required but does not replace review.

## Developer Certificate of Origin

Hushmark uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/) and does
not require a separate contributor license agreement. Sign off every commit:

```bash
git commit -s -m "feat: describe the change"
```

The sign-off certifies that you have the right to submit the contribution under the project license.
Use your real name or another identity you are legally entitled to use for this certification.

## Review and release

Review follows [GOVERNANCE.md](GOVERNANCE.md). Maintainers may edit commit structure during merge
while preserving attribution and sign-offs. Public packages and images are released only through the
repository workflows; do not publish them manually from a contributor account.
