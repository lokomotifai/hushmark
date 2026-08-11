# Governance

## Model

Hushmark is founder-led and developed in public. The maintainer listed in
[MAINTAINERS.md](MAINTAINERS.md) is accountable for project direction, release integrity, security
coordination, and final merge decisions.

## How decisions are made

- Small, reversible changes are decided through normal issue and pull-request review.
- User-visible behavior, public APIs, taxonomy changes, security boundaries, and repository
  structure should be discussed in an issue before implementation.
- Large or difficult-to-reverse decisions should include an ADR or design note with alternatives,
  operational impact, migration cost, and security implications.
- Consensus is preferred. When consensus is not possible, the maintainer records the decision and
  rationale in the public issue or pull request.

## Contributions and review

Anyone may report issues, propose designs, review changes, or submit a pull request under
[CONTRIBUTING.md](CONTRIBUTING.md). Merge rights are granted for sustained contribution and sound
judgment. No contributor receives preferential technical treatment because of employer, customer,
or commercial status.

The maintainer should disclose material conflicts of interest and seek additional public review when
a decision could benefit an affiliated party at the project’s expense.

## Security exceptions

Active vulnerabilities may be handled privately under [SECURITY.md](SECURITY.md). Once disclosure is
safe, the fix and relevant rationale should return to the public record without exposing reporters or
exploit details unnecessarily.

## Continuity

If the current maintainer can no longer serve, they should nominate an active contributor with the
best demonstrated technical and community judgment. If no handoff is possible, active contributors
may document a transition proposal in a public issue and update MAINTAINERS.md by consensus.
