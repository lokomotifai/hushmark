# Hushmark administration guide

## Daily checks

1. Confirm `/readyz` is ready and its transitive core check succeeds.
2. Compare dashboard mask/block counts with expected traffic.
3. Verify the audit chain and escalate any broken chain to incident response.
4. Monitor license state, expiry, and the grace window.

## Policy management

The policy matrix uses the closed 24-type taxonomy. Unknown types, unknown actions, and multimodal
content fail closed. Export the current policy before a change, make the smallest scoped update,
and verify one masked and one blocked example against the fake upstream. Buffered response scan is
incompatible with streaming.

## Roles and de-mask

`admin` manages policy and identities. `operator` may resolve authorized placeholders. `auditor`
can inspect audit events and chain results but cannot resolve values. Constrain de-mask operations
with a reason, session, and evidence event.

## License lifecycle

Entitled management features operate while the license is valid or in grace. After grace,
configuration becomes read-only/frozen while runtime traffic continues. Validate a replacement
license and public key together; never place the issuer private key on a runtime system.

## Incident response

When core is unreachable, gateway fails closed with 503. If audit verification fails, export the
relevant NDJSON into immutable evidence storage, compare the last known anchor, and investigate
write access. Do not paste placeholder values or customer text into logs.
