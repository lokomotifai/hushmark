# Security model

Hushmark reduces the amount of configured PII forwarded to supported LLM providers. Reversible
masking preserves utility but keeps a protected mapping capable of restoring the original value.

## Trust boundaries

1. Client → gateway: authenticated request boundary; untrusted request shape and text.
2. Gateway → core: service-token-authenticated private detection boundary; core is not externally exposed.
3. Gateway → provider: only policy-processed request fields cross this egress boundary.
4. Gateway → vault/KMS/database: enterprise custody and evidence boundary.
5. Operator → admin API/console: authenticated RBAC boundary.
6. Build system → release artifact: allowlisted source and corpus-leak boundary.

## STRIDE analysis

| Threat                 | Representative risk                                   | Implemented controls                                                                                                                                           | Residual risk                                                                                     |
| ---------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Spoofing               | Stolen gateway or admin credential                    | Bearer-key validation, argon2id local admin auth, RBAC, secret-backed Helm config                                                                              | Credential lifecycle and enterprise SSO operations remain deployment responsibilities             |
| Tampering              | Policy, audit, image, or license modification         | Strict schemas, HMAC-SHA-256/JCS audit chain, runtime model digest verification, ed25519 license, digest pins, keyless Cosign signatures and SBOM attestations | External audit-anchor custody and customer verification policy remain deployment responsibilities |
| Repudiation            | Operator denies de-mask/export action                 | Role-bound audit events, sequence and previous-hash linkage, verify CLI                                                                                        | Host administrators can affect local storage; export anchors externally                           |
| Information disclosure | Raw values reach provider, logs, image, or mirror     | Mask-before-forward, fail-closed core boundary, no-body logging tests, KMS envelope vault, allowlist/canary scans                                              | Detection false negatives, authorized de-mask, memory access, and buffered-response limits remain |
| Denial of service      | Core/model/upstream unavailable or oversized traffic  | Rate limits, body/concurrency limits, health/readiness, timeouts, bounded TTL/LRU vault, Kubernetes resources, fail-closed behavior                            | Capacity planning and provider availability are external                                          |
| Elevation of privilege | Auditor resolves values or workload gains host rights | Explicit RBAC tests, non-root containers, dropped capabilities, read-only filesystems, no service-account token                                                | Cluster and cloud IAM configuration remains customer-controlled                                   |

## Non-goals

- Reversible masking is not anonymization.
- The detector does not prove that text contains no PII.
- Streaming response-side scanning is not provided in v0.1; buffered mode is explicit.
- The open in-memory vault is single-instance and non-persistent.
- Hushmark does not replace provider governance, data-retention review, legal analysis, DLP at other
  egress points, endpoint security, or Kubernetes/cloud hardening.

## Reporting

Do not include customer text, placeholders' original values, credentials, or issuer private keys in
an issue. Report the affected version, route, configuration class, reproducible sanitized input,
and whether the finding crosses a listed trust boundary.
