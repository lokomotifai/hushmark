# Security policy

Do not open a public issue for suspected vulnerabilities or include real personal data,
credentials, customer payloads, or exploit details in public discussions.

Use [GitHub private vulnerability reporting](https://github.com/hushmark/hushmark-open-core/security/advisories/new)
when available. If that channel is unavailable, email `fatih@komunite.com.tr` with the subject
`Hushmark security report`. Include affected versions, impact, and safe reproduction steps.

We aim to acknowledge reports within three business days and provide an initial assessment within
seven business days. These are best-effort targets for a small maintainer team, not an SLA.

The latest `0.1.x` release is supported. `main` is the development branch; older prereleases and
unpinned images are not supported. Fixes are developed in the canonical
[`hushmark/hushmark`](https://github.com/hushmark/hushmark) repository and propagated to this mirror
when they cross its source boundary.

Good-faith research is welcome when it avoids privacy violations, disruption, social engineering,
data destruction, and access beyond what is needed to demonstrate the issue. This does not authorize
testing systems you do not own or have permission to test. See the detailed
[security model](docs/security.md) for architecture assumptions and residual risks.
