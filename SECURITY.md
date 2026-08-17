# Security policy

## Reporting a vulnerability

Please do not open a public issue for suspected vulnerabilities or include real personal data,
credentials, customer payloads, or exploit details in public discussions.

Use [GitHub private vulnerability reporting](https://github.com/lokomotifai/hushmark/security/advisories/new)
when available. If that channel is unavailable, email `fatih@komunite.com.tr` with the subject
`Hushmark security report`. Include affected versions, impact, reproduction steps, and any suggested
embargo needs. Encrypt sensitive material before sending and first ask for a suitable transfer
channel if necessary.

We aim to acknowledge reports within three business days, provide an initial assessment within seven
business days, and keep the reporter informed until remediation or closure. These are best-effort
targets for a small maintainer team, not an SLA.

## Supported versions

| Version                               | Security fixes                                     |
| ------------------------------------- | -------------------------------------------------- |
| Latest `0.1.x` release                | Supported                                          |
| `main`                                | Development branch; fixes land here before release |
| Older prereleases and unpinned images | Not supported                                      |

## Coordinated disclosure

We will validate the report, determine affected components, prepare a fix and advisory, and agree on
a disclosure timeline that protects users. Please allow a reasonable remediation window. We credit
reporters who request attribution and preserve anonymity when requested.

Good-faith research intended to improve Hushmark security is welcome when it avoids privacy
violations, service disruption, social engineering, data destruction, and access beyond what is
needed to demonstrate the issue. This statement does not authorize testing systems you do not own
or have permission to test.

## What is in scope

In scope: anything that lets configured personal data cross the boundary unmasked, that resolves a
placeholder outside its scope or role, that forges or breaks the audit chain, that reads original
values from logs, exports, images, or the open-core mirror, that bypasses gateway or admin
authentication, or that allows an unverified model or image to load.

Detection quality is generally **not** a vulnerability. A missed or misclassified entity is a
measurable defect, and the right route for it is a
[bug report](https://github.com/lokomotifai/hushmark/issues/new?template=bug.yml) with a synthetic
reproduction. It becomes a security report when the miss is systematic and triggerable on purpose —
an input construction that reliably defeats a validator, for example — because that is an evasion
technique rather than a coverage gap.

Also out of scope: findings that depend on a deployment ignoring the documented controls, on the
evaluation Compose profile's deliberately non-production credentials, or on the open runtime's
documented limitations such as its non-persistent in-memory vault.

## Where the boundaries are documented

For architecture assumptions, trust boundaries, the STRIDE analysis with residual risks, signature
verification, and deployment controls, see the detailed [security model](docs/security.md). The
reasoning behind the fail-closed boundary, the vault design, and model verification is recorded in
[`docs/adr/`](docs/adr/). Tooling and practices are summarized in machine-readable form in
[SECURITY-INSIGHTS.yml](SECURITY-INSIGHTS.yml).

None of those documents is an audit result or a certification. They describe what the project does
and what it has not established.
