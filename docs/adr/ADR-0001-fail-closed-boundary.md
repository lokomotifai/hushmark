# ADR-0001: The gateway fails closed when detection is unavailable

- Status: Accepted
- Date: 2026-08-10
- Scope: gateway, core

## Context

The gateway sits on the request path between an application and an AI provider. Its whole purpose is
that no configured personal data crosses that boundary unexamined. Core, which performs detection,
is a separate service, and separate services fail: a restart, a model load, an out-of-memory
condition, a network partition, or a slow first inference.

At that moment the gateway has exactly two options. It can forward the request unmasked, keeping the
application working and silently disabling the control. Or it can refuse the request, breaking the
application in a way its operators will notice.

The first option is more attractive than it sounds. Availability pressure is real, and "degrade
gracefully" is normally good engineering advice.

## Decision

The gateway fails closed. When the detection boundary cannot be reached or cannot answer, the
request is refused with an error. There is no unmasked fallback path, no timeout that results in
forwarding, and no configuration flag that enables one.

`/readyz` on the gateway includes a transitive core check, so an orchestrator sees the dependency
before traffic arrives rather than after.

## Alternatives considered

**Forward unmasked with a warning log.** Rejected. A control that turns itself off under load
produces its worst behavior exactly when the system is under stress, and the resulting exposure is
invisible until someone reads the logs. Nobody reads the logs.

**Forward with deterministic detection only, skipping the model.** Rejected as a default. It is a
coherent position—L0 alone still catches every checksummed identifier—but it silently changes the
security properties of the deployment without the operator choosing that trade-off. If a deployment
wants that behavior it should be an explicit configuration of what runs, not an implicit
consequence of a failure.

**Queue and retry.** Rejected for the synchronous request path. Masking runs inline; a queue moves
the failure rather than handling it.

## Consequences

Hushmark's availability is bounded by core's availability, and a deployment must plan for that:
resource limits, readiness gating, and capacity for the selected model backend. The
[production Compose](../install-compose-production.md) and [Helm](../install-helm.md) guides treat
core as a hard dependency rather than an optional enhancement.

The failure is loud, which is the point. An operator finds out that detection is down because
requests stop, not because a quarterly log review finds unmasked identifiers in a provider account.

## Security and privacy impact

This is the property most of the rest of the system relies on. Removing it would make every other
guarantee conditional on nothing having gone wrong, which is not a guarantee.

Note the scope limit: failing closed protects the request path. It does not protect against
detection that runs successfully and misses something, which is a different problem measured in
[the engine comparison](../benchmark-comparison.md).
