# Governance

Hushmark is developed in public. Governance exists to make authority legible: who may decide, what
evidence a decision needs, how a contributor earns trust, and how the project can outlive any one
person.

The project is currently **founder-led**. That describes its present capacity; it is not a permanent
entitlement or a claim of community consensus. Current people and scopes are recorded in
[MAINTAINERS.md](MAINTAINERS.md).

## Governing principles

1. **Authority is explicit.** Repository, release, security, and moderation authority is granted by
   role and scope. A title alone grants nothing.
2. **Decisions leave a record.** A material decision states the problem, the alternatives, the
   trade-offs, and who is accountable for the outcome.
3. **Trust follows demonstrated stewardship.** Code, documentation, review, triage, security work,
   evaluation evidence, and community care all count as contribution.
4. **Claims require evidence.** A green check, a document, or a role does not by itself prove a
   detection, deployment, or supply-chain property. This applies to the project's own claims first.
5. **The project does not pretend to be larger than it is.** Committees and voting bodies are
   created when named people accept those duties, not before.

## Roles

Roles are additive and may be scoped to core, gateway, console, deployment, documentation,
evaluation, releases, security, or community moderation.

**Contributor.** Anyone who improves Hushmark through an issue, review, test, design note,
documentation change, code change, translation, or community support. No merged pull request or
organization membership is required for the label. Contributors may propose work and take part in
every public decision. They do not merge changes, publish releases, access private security reports,
or speak for the project unless a maintainer explicitly delegates that.

**Reviewer.** Someone who has shown reliable judgment in a named scope. Reviewers triage issues and
give reviews that maintainers rely on for acceptance, but do not receive merge or release authority
by default. There is no contribution count that automatically confers the role.

**Maintainer.** Accountable for a documented scope and able to approve and merge changes in it.
Maintainers are expected to protect compatibility, security invariants, and honest product claims;
to review other people's work rather than only advancing their own; to explain consequential
decisions and disclose material conflicts; to keep issues moving or hand them off clearly; to use
two-factor authentication; and to mentor contributors toward greater responsibility.

**Emeritus maintainer.** Recognized for past stewardship, holding no current authority. Returning to
an active role uses the normal appointment process so access reflects current context.

Repository administration, package and image publication, release approval, model artifact
publication, private vulnerability access, and conduct response are separate capabilities. They are
listed explicitly in [MAINTAINERS.md](MAINTAINERS.md) and are never implied by generic maintainer
status.

## Contributor ladder

Role changes are proposed by pull request to `MAINTAINERS.md`. The proposal identifies the scope,
summarizes the candidate's relevant work, describes the authority requested, and records the
candidate's consent.

During the founder-led stage the repository owner appoints reviewers and maintainers and publishes
the rationale. Once two or more active maintainers exist, an appointment requires support from two
active maintainers, no unresolved substantiated objection, and at least seven calendar days of
public comment. A candidate never approves their own appointment.

Roles are reviewed when the holder has been inactive for six months, can no longer meet the role's
security requirements, asks to step down, or repeatedly fails the responsibilities above. Removal
follows notice and a chance to respond, except where immediate revocation is needed to contain a
security or safety risk. The non-sensitive outcome is recorded publicly.

## Decision classes

| Class            | Examples                                                                                                                            | What it requires                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Routine**      | Bug fix, test, documentation correction, dependency bump, internal refactor with no contract change                                 | Normal pull-request review by someone other than the author.                                                        |
| **Notable**      | New configuration option, new deployment profile, new benchmark adapter, user-visible message or console change                     | An issue first, then review. The pull request states the compatibility and privacy impact.                          |
| **Material**     | Public API or schema change, placeholder format, error-code semantics, policy evaluation order, default detection thresholds        | An issue, an explicit migration note, and a maintainer decision recorded in the thread.                             |
| **Foundational** | Taxonomy changes, the fail-closed boundary, vault or audit-chain design, adopted model replacement, licensing, repository structure | A written decision record in [`docs/adr/`](docs/adr/) with alternatives, operational impact, and security analysis. |

When a change spans classes, the highest class applies. Reversibility is the deciding factor: the
harder a decision is to undo for existing deployments and stored evidence, the more record it needs.

## Proposals, RFCs, and decision records

Anyone may open a proposal. Small proposals live in an issue. Anything foundational, or anything
where reasonable people would choose differently, becomes a decision record.

A decision record is a pull request adding a numbered file to `docs/adr/`. It states the context,
the decision, the alternatives considered and why they were rejected, the consequences including
what becomes harder, and the security and privacy impact. Records are immutable once accepted: a
later decision supersedes an earlier one by adding a new record and marking the old one superseded,
rather than by editing history.

Records may be proposed by any contributor. Acceptance is a maintainer decision under the ladder
above. A record that is rejected stays in the pull-request history as part of the public reasoning.

## How decisions are made

Consensus is preferred. Discussion happens in the open issue or pull request so that the reasoning
is available later, not only the outcome. When consensus is not reached, the accountable maintainer
decides and records the rationale in the same public thread.

No contributor receives preferential technical treatment because of employer, customer, or
commercial status. A maintainer must disclose material conflicts of interest and seek additional
public review when a decision could benefit an affiliated party at the project's expense. Paid
support or commercial relationships, if they exist, do not change public issue priority, review
standards, or governance rights.

## Security exceptions

Active vulnerabilities are handled privately under [SECURITY.md](SECURITY.md), including work that
would normally require a public decision record. Once disclosure is safe, the fix and its rationale
return to the public record without unnecessarily exposing reporters or exploit detail. A security
fix may ship before its decision record is written; the record still gets written.

## Continuity

If the current maintainer can no longer serve, they should nominate an active contributor with the
best demonstrated technical and community judgment, and transfer the capabilities listed in
`MAINTAINERS.md` deliberately rather than all at once. If no handoff is possible, active
contributors may document a transition proposal in a public issue and update `MAINTAINERS.md` by
consensus.

Publication credentials, signing identities, and the model artifact account are project assets, not
personal ones. A departing maintainer rotates or hands over every credential in their scope, and the
change is recorded in `MAINTAINERS.md`.
