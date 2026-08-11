# Contributing to Hushmark Open Core

Thank you for helping improve Hushmark. By participating, you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md) and license contributions under [Apache-2.0](LICENSE).

This repository is an allowlist-generated release mirror. To prevent the next extraction from
overwriting work:

- propose detector, gateway, SDK, benchmark, or taxonomy code changes in the canonical
  [`hushmark/hushmark`](https://github.com/hushmark/hushmark) repository;
- use this repository for mirror-specific documentation, packaging, release, or community fixes;
- open an issue first if you are unsure which boundary owns the change.

Never commit credentials, personal data, customer payloads, private corpora, or model weights.
Report vulnerabilities privately under [SECURITY.md](SECURITY.md).

## Verify a change

Prerequisites are Node.js 22, pnpm 9, Python 3.12, and uv.

```bash
./scripts/bootstrap.sh
./scripts/verify.sh
```

Pull requests should explain the problem, behavior, tests, and privacy/security impact. Keep changes
focused. Passing CI is required but does not replace maintainer review.

## Developer Certificate of Origin

Hushmark uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/) and does
not require a CLA. Sign off every commit with `git commit -s`. The sign-off certifies that you have
the right to submit the contribution under the project license.
