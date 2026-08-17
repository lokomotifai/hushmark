# Maintainers

Hushmark uses a founder-led maintenance model. This file records who currently holds which
authority, so that neither the project nor its users have to infer it.

## Active maintainers

| Maintainer  | GitHub                                       | Scope                                                                              |
| ----------- | -------------------------------------------- | ---------------------------------------------------------------------------------- |
| Fatih Guner | [@fatihguner](https://github.com/fatihguner) | All scopes: core, gateway, console, deployment, evaluation, documentation, release |

## Sensitive capabilities

These are separate grants. Generic maintainer status does not imply any of them, and each is listed
so that a compromise is easier to reason about.

| Capability                       | Held by     | Notes                                                                     |
| -------------------------------- | ----------- | ------------------------------------------------------------------------- |
| Repository administration        | Fatih Guner | Branch protection, secrets, workflow permissions, CODEOWNERS.             |
| Release approval and tagging     | Fatih Guner | Immutable releases are restricted to `main` by workflow policy.           |
| PyPI and npm publication         | Fatih Guner | Publication happens through repository workflows, never from a laptop.    |
| Container image publication      | Fatih Guner | `ghcr.io/lokomotifai/*`, signed with keyless Cosign.                      |
| Model artifact publication       | Fatih Guner | `lokomotifai/hushmark-tr-289m`; digests are pinned in `core/models.yaml`. |
| Open-core mirror generation      | Fatih Guner | Allowlist-driven; gated by secret and corpus-leak scans.                  |
| Private vulnerability reports    | Fatih Guner | GitHub private reporting and the security contact below.                  |
| Code of Conduct response         | Fatih Guner | See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the escalation path.     |
| License issuer keys (enterprise) | Fatih Guner | Kept outside this repository; never committed.                            |

Single-person custody of every capability is a real continuity risk and is recorded here rather than
hidden. [GOVERNANCE.md](GOVERNANCE.md) describes how capabilities are transferred or rotated when
maintainership changes.

## Verified contact routes

- Security reports: [GitHub private vulnerability reporting](https://github.com/lokomotifai/hushmark/security/advisories/new),
  or `fatih@komunite.com.tr` with the subject `Hushmark security report` if that channel is
  unavailable. See [SECURITY.md](SECURITY.md).
- Conduct reports: `fatih@komunite.com.tr`.
- Trademark and branding questions: `fatih@komunite.com.tr`.
- Everything else: a public issue, using the routes in [SUPPORT.md](SUPPORT.md).

Only routes listed here are official. The project does not conduct support, security, or release
business through direct messages on social platforms, and will never ask you for credentials, a
production log, or customer data.

## Becoming a maintainer

Maintainer status reflects active responsibility, not ownership of contributors' copyrights. New
reviewers and maintainers are added after sustained, constructive contribution and demonstrated
judgment in the relevant area, through the ladder in [GOVERNANCE.md](GOVERNANCE.md). Changes to this
file are made by pull request.

The project intentionally does not list inactive people or fictional committees. If maintenance
capacity changes, the continuity section of `GOVERNANCE.md` applies.
