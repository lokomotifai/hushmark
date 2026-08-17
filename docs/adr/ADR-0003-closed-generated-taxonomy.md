# ADR-0003: The v0.1 taxonomy is closed and generated into every language surface

- Status: Accepted
- Date: 2026-08-10
- Scope: taxonomy, core, gateway, console, SDKs

## Context

The entity taxonomy is consumed by a Python detection core, a TypeScript gateway, a TypeScript
console, two SDKs, the benchmark harness, and the audit record. Each one needs the type list, the
KVKK classification, the default action, and the Turkish label.

Anything maintained by hand in six places drifts. Here the drift is not cosmetic: a type present in
the core but missing from the gateway's policy schema is a type that gets detected and then
forwarded anyway.

## Decision

`taxonomy/taxonomy.yaml` is the single source. It defines each type's layer, KVKK class, default
action, Turkish label, and description. Cross-language types are generated from it, and
`scripts/verify.sh` fails if any generated file does not match what the generator produces.

The taxonomy is **closed** for v0.1. Adding, removing, or reclassifying a type is a foundational
decision under [GOVERNANCE.md](../../GOVERNANCE.md) and requires its own record.

## Alternatives considered

**An open, operator-extensible type registry.** Deferred rather than rejected. It is a reasonable
eventual feature, but in v0.1 it would mean custom types appearing in stored placeholders and audit
records with no stable definition, no benchmark coverage, and no migration story. That is a
compatibility problem that gets worse with time.

**Hand-written types in each language with a test that compares them.** Rejected. It is the same
work as generation with more opportunities to be wrong.

**A runtime-loaded taxonomy.** Rejected for v0.1. It moves a security-relevant definition out of
the reviewed artifact and into deployment configuration.

## Consequences

Changing the taxonomy is deliberately awkward. That is proportionate: placeholders like `[HEALTH_1]`
appear in vault entries and audit chains that outlive the request, so a type name is closer to a
storage schema than to a label.

Operators are not blocked by the closed list, because the policy layer is where per-type actions,
thresholds, and per-tenant behavior are configured. What is closed is the vocabulary, not the
behavior.

## Security and privacy impact

Every surface agrees on what a type means and what its default action is. Eight special-category
types default to `block` rather than `mask` in one place, and that default cannot be silently
different in the console than in the core.

Generated files carry a header saying they are generated. Editing one by hand is a review finding,
not a matter of taste.
