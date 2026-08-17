# ADR-0002: Deterministic validators own checksummed identifiers; the model owns semantics

- Status: Accepted
- Date: 2026-08-10
- Scope: core

## Context

The 24 entity types Hushmark recognizes are not one kind of thing. A TCKN either satisfies its
checksum or it does not. "Union membership" has no format at all; it is a claim expressed in
ordinary Turkish that varies by sentence.

Treating both with one mechanism goes badly in either direction. A pure regular-expression system
cannot see special-category data. A pure model must learn to imitate arithmetic it will never
perform reliably, and its confidence on a national identity number will always be a probability
rather than a fact.

## Decision

Detection has two layers with a strict division of ownership.

**Layer 0** owns the twelve deterministic types: TCKN, VKN, Turkish and other IBANs, credit cards,
phone numbers, plates, SGK numbers, email addresses, and the three secret types. Each has a
validator that verifies structure and, where one exists, a checksum: ISO 7064 mod-97 for IBAN, Luhn
for cards, the published algorithms for TCKN and VKN. A candidate that fails its rule is not an
entity.

**Layer 1** owns the twelve semantic types: person, address, organization, date of birth, and the
eight KVKK article 6 special categories. The model proposes spans; the spans are scored against a
threshold; policy decides what happens to them.

The model is never asked to produce the deterministic types, and its label set in
`core/models.yaml` contains only the twelve it owns.

## Alternatives considered

**One model for all 24 types.** Rejected, and later measured. A fine-tuned model evaluated without
the deterministic layer reaches `0.322` recall on the Turkish identifier group, missing TCKN, VKN,
SGK, non-Turkish IBAN, and JWT entirely. Those are the types where a miss is most expensive.

**Regular expressions plus a keyword list for special categories.** Rejected. Turkish morphology and
the open-ended vocabulary of health, belief, and political expression defeat lexical matching, and a
keyword list creates a false sense of coverage that is hard to audit.

**Model proposals filtered by validators.** Rejected as the primary path because it makes the
guarantee depend on the model finding the candidate first. The validators scan the text directly.

## Consequences

Two code paths must stay in sync with one taxonomy, which is why the taxonomy is generated rather
than hand-maintained (see [ADR-0003](ADR-0003-closed-generated-taxonomy.md)).

The layers can be reasoned about separately, which makes the system auditable: "why was this
masked?" has a different and better answer for a TCKN than for a name, and both answers are
available.

A useful side effect is the deterministic residual short circuit: input fully handled by Layer 0
does not need to invoke the model at all.

## Security and privacy impact

The types where a false negative is most damaging—national identifiers, financial identifiers,
credentials—are the types that do not depend on model behavior, model version, threshold tuning, or
inference backend. Their recall is a property of arithmetic, and it is reproducible.

The measured contribution of each layer is documented in the ablation section of
[the engine comparison](../benchmark-comparison.md).
