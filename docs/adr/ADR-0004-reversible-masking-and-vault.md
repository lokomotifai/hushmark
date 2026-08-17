# ADR-0004: Masking is reversible through a scoped vault, and is not anonymization

- Status: Accepted
- Date: 2026-08-10
- Scope: core, gateway, gateway-enterprise

## Context

A support agent asking an assistant about a customer's account needs the answer to name that
customer. A summarizer needs the addresses in the document it summarizes to still be
distinguishable. Irreversible redaction produces output that is safe and useless.

Reversibility is therefore a product requirement, not a compromise. But it has an unavoidable
consequence: a mapping from placeholder to original value exists somewhere, and whoever holds it
holds the personal data.

## Decision

Detected spans are replaced with placeholders of the form `[TYPE_N]`, where `N` counts occurrences
of that type within the request scope. Equal values within a scope receive the same placeholder, so
the text stays coherent for the model. The mapping is stored in a vault scoped to the session, and
restoration on the response path resolves only placeholders that scope actually issued.

Input that already contains placeholder grammar is a collision, and the default behavior is to
reject the request rather than to guess. The alternative mode appends a random suffix so that
attacker-supplied text cannot impersonate an issued placeholder.

The open runtime's vault is in-memory, TTL- and LRU-bounded, and does not survive a restart. The
enterprise runtime's vault is persistent and encrypted under a KMS envelope, with role-gated
resolution and an audit event for every de-mask.

Every surface states that this is a technical security measure and not anonymization. A
claim-language lint in `scripts/verify.sh` rejects the phrasings that blur that line.

## Alternatives considered

**Irreversible redaction.** Rejected as the default; it eliminates the use cases the product
exists for. It remains available in effect through the `block` action for types where no answer is
better than a masked answer, which is why eight special-category types default to `block`.

**Format-preserving encryption or tokenization of the value itself.** Rejected for v0.1. It removes
the separate mapping store, but produces tokens that leak length and character class, and it moves
the security of the system onto key management for every value rather than for one vault.

**Deterministic per-tenant placeholders, stable across requests.** Rejected as a default. It makes
placeholders correlatable across sessions, which turns them into pseudonymous identifiers with
their own linkage risk. Stable continuity within a conversation is available explicitly through a
scoped session.

## Consequences

The vault is the most sensitive component in the system, and its custody is a first-class
operational concern rather than an implementation detail. The open runtime's non-persistent vault is
a deliberate limitation, not an unfinished feature: a single-host pilot should not accumulate a
durable store of original values by accident.

Restoration is bounded by scope. A placeholder from another session does not resolve, and an
unknown placeholder passes through unchanged rather than erroring.

## Security and privacy impact

Reversible masking reduces what reaches a provider. It does not make the data anonymous, it does not
by itself satisfy any legal obligation, and it creates a custody obligation where none existed
before. Saying so plainly in the README, the SDKs, the console, and the reports is part of the
decision, not a disclaimer attached to it.
