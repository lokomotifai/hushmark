# Architecture decision records

These records explain why Hushmark's boundaries are where they are. They exist so that a
contributor, an operator, or a security reviewer can evaluate a decision on its stated reasoning
rather than reconstructing it from the code.

A record states the context, the decision, the alternatives that were rejected and why, the
consequences including what became harder, and the security and privacy impact. Records are
immutable once accepted: a later decision supersedes an earlier one by adding a new record and
marking the old one superseded, never by editing it.

[GOVERNANCE.md](../../GOVERNANCE.md) defines which changes require a record. In short: anything
foundational—the taxonomy, the fail-closed boundary, vault or audit design, model adoption,
licensing, repository structure—and anything where reasonable people would choose differently.

| Record                                               | Decision                                                                       | Status   |
| ---------------------------------------------------- | ------------------------------------------------------------------------------ | -------- |
| [ADR-0001](ADR-0001-fail-closed-boundary.md)         | The gateway fails closed when detection is unavailable                         | Accepted |
| [ADR-0002](ADR-0002-two-layer-detection.md)          | Deterministic validators own checksummed identifiers; the model owns semantics | Accepted |
| [ADR-0003](ADR-0003-closed-generated-taxonomy.md)    | The v0.1 taxonomy is closed and generated into every language surface          | Accepted |
| [ADR-0004](ADR-0004-reversible-masking-and-vault.md) | Masking is reversible through a scoped vault, and is not anonymization         | Accepted |
| [ADR-0005](ADR-0005-code-point-offsets.md)           | Offsets are Unicode code points, end-exclusive, on every surface               | Accepted |
| [ADR-0006](ADR-0006-open-core-mirror.md)             | The public mirror is generated from an explicit allowlist                      | Accepted |
| [ADR-0007](ADR-0007-model-distribution.md)           | Model weights are distributed by pinned revision and digest, never in Git      | Accepted |

## Writing a new record

Copy the structure of an existing record, take the next free number, and open a pull request. Do not
renumber existing records. A rejected proposal stays in the pull-request history as part of the
public reasoning; it is not merged as a record.
