# ADR-0006: The public mirror is generated from an explicit allowlist

- Status: Accepted
- Date: 2026-08-13
- Scope: repository, release

## Context

Hushmark's detection core, gateway, SDKs, benchmark, and taxonomy are open source. The same
repository also contains material that is not: private evaluation corpora, strategy and research
notes, the license issuer, and deployment secrets scaffolding.

Two obvious approaches both fail. Publishing the whole repository publishes things that must not be
published. Maintaining a separate public repository by hand guarantees that the two diverge, and the
divergence is discovered by a user filing a bug against code that no longer exists upstream.

## Decision

[`hushmark-open-core`](https://github.com/lokomotifai/hushmark-open-core) is generated from this
repository through an explicit allowlist. A path is published because it is named, not because it
was not caught by an exclusion rule.

This repository is the canonical development history. Code changes to the mirrored components must
target it first; a pull request opened against the mirror cannot be merged back.

Generation is gated. `scripts/check-repository-safety.sh` and `scripts/check-build-context.sh` run
in `verify.sh`, and the release path adds secret and corpus-leak scans plus a container image canary
before anything is published.

## Alternatives considered

**A denylist.** Rejected. A denylist fails open: a new directory is published by default, and the
mistake is only visible after it is public and mirrored by others. An allowlist fails closed—a new
public component is simply missing until someone adds it, which is a bug report rather than a
disclosure.

**Git history rewriting into a public repository.** Rejected. Filtered history is difficult to
verify, and a single missed blob in an old commit is permanent.

**Separate repositories from the start.** Rejected. It splits review, CI, and version alignment
across repositories for a project with one maintainer, and cross-repository changes become the
normal case rather than the exception.

## Consequences

The mirror carries source only. It has no adopted model weights, no private corpora, no console, no
persistent vault, no RBAC, no audit evidence, and no license issuer. Its README says so explicitly,
so a reader does not conclude that the mirror is the whole product.

Public releases are tagged on the mirror, which is why the release badge in the README points there
while the CI badges point here. This is stated in the README rather than left to be inferred.

Contributors need to know which repository to target. `CONTRIBUTING.md` says so in the first
section.

## Security and privacy impact

The controlling property is that publication is opt-in per path and verified by executable checks
rather than by reviewer attention. The failure mode of the chosen design is an omission; the failure
mode of the rejected design is a disclosure.
