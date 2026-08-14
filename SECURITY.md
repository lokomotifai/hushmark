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

For architecture assumptions, residual risks, signature verification, and deployment controls, see
the detailed [security model](docs/security.md).
