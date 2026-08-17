# Contributing to Hushmark

Hushmark welcomes code, tests, documentation, translation, review, issue triage, design critique,
and reproducible evaluation evidence. Contributions are judged by the clarity of the problem and
the strength of the evidence for the outcome—not by their size or by a contributor's prior
visibility.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md) and to license your
contribution under [Apache-2.0](LICENSE).

## Start with the right conversation

- **Small bug or documentation fix:** a focused pull request is welcome.
- **Unclear bug:** open a [bug report](https://github.com/lokomotifai/hushmark/issues/new?template=bug.yml)
  with a minimal, safely shareable reproduction.
- **New capability, public API, or taxonomy change:** open a
  [feature proposal](https://github.com/lokomotifai/hushmark/issues/new?template=feature.yml)
  before implementation. The v0.1 taxonomy is closed; changing it affects generated code in three
  languages, stored placeholders, and audit history.
- **Security vulnerability:** use [private reporting](SECURITY.md), never a public issue or pull
  request.

Read the relevant package README, the [security model](docs/security.md), and the accepted
decisions in [`docs/adr/`](docs/adr/) before changing a public contract. Comment on an issue before
taking substantial unassigned work; assignment avoids duplicated effort but does not reserve an
issue indefinitely.

The full [`lokomotifai/hushmark`](https://github.com/lokomotifai/hushmark) repository is the
canonical development history. [`hushmark-open-core`](https://github.com/lokomotifai/hushmark-open-core)
is generated from an explicit allowlist, so core, gateway, SDK, benchmark, and taxonomy changes
must target this repository first. A pull request opened against the mirror cannot be merged back.

## Development setup

Requirements:

- Node.js 22 and the exact pnpm version declared in `packageManager` (`10.34.4`).
- Python 3.12 and [uv](https://docs.astral.sh/uv/).
- Docker with Compose v2 for the integration and deployment paths.
- Roughly 8 GiB of free memory and 3 GiB of disk for the model stack.

```bash
git clone https://github.com/lokomotifai/hushmark.git
cd hushmark
./scripts/bootstrap.sh
./scripts/verify.sh
```

`bootstrap.sh` installs both locked workspaces, then downloads the pinned model revision and
verifies every file against the SHA-256 digests in `core/models.yaml`. Pass
`HUSHMARK_FETCH_MODELS=0` to skip the download. Model-backed tests need those weights; the rest of
the suite runs without them.

Lockfiles are a supply-chain control. Do not add a dependency without stating in the pull request
what it does, who maintains it, and why a smaller option does not work. Required behavior must be
testable without a live provider key or a paid account.

Run the smallest relevant check while iterating:

```bash
pnpm lint          # or pnpm typecheck / pnpm test
uv run pytest      # or uv run ruff check … / uv run mypy …
```

Run `./scripts/verify.sh` before requesting review. If your environment cannot run one of its
checks, run every other available check and state the exact unrun command and the reason in the
pull request; a maintainer decides whether CI supplies the missing evidence.

## Engineering contract

- Keep public code, API names, error codes, and canonical documentation in English. Turkish
  companion content must keep semantic and safety parity, including `README.tr.md` and the operator
  guide.
- Treat every request body, provider response, and model output as untrusted until validation
  succeeds. Detection is a signal; policy, masking, blocking, and audit decisions stay outside the
  model.
- Preserve the fail-closed boundary. A change that lets a request reach a provider when detection is
  unavailable will not be accepted, however convenient the fallback is.
- Offsets are Unicode code points and end-exclusive on every surface. Do not introduce a UTF-16 or
  byte-offset path.
- Never log, export, or serialize request bodies, original values, or resolved placeholders. There
  are tests for this; keep them passing rather than adjusting them.
- Change generated files through their source definition and generator, never by hand. The taxonomy,
  cross-language types, and `docs/api-reference.md` all have generators, and `verify.sh` proves they
  match.
- Add deterministic tests for success and for the interesting failures: malformed input, denial,
  boundary offsets, concurrency, and restart behavior.
- Do not commit credentials, personal data, customer payloads, private corpora, or model weights.
  Keep synthetic fixtures obviously synthetic and safe to publish.
- Do not claim compliance, anonymization, certification, or accuracy beyond what an executable check
  in this repository demonstrates. `verify.sh` includes a claim-language lint, and a reviewer will
  also read for claims that are wider than the evidence.

## Commit certification

Hushmark uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/) and does
not require a Contributor License Agreement. Every commit must carry a sign-off:

```text
Signed-off-by: Your Name <your-email@example.com>
```

Create it with `git commit -s`. A pull-request checkbox does not replace per-commit sign-off. The
sign-off certifies that you have the right to submit the contribution under the project license;
use your real name or another identity you are legally entitled to use for that certification.
Amend or rebase your own unsigned commits, but never rewrite another contributor's certification.

## AI-assisted contributions

Tool assistance is allowed; unreviewed generated output is not. The human who signs the commit is
responsible for authorship rights, technical accuracy, security, tests, citations, and every line
retained.

Do not submit generated prose or code you cannot explain, open speculative issues in bulk, fabricate
benchmark or test evidence, or use automation to imitate community support. If a generative tool
produced a substantial portion of the retained change, say so briefly in the pull request and
describe how you verified it. You do not need to publish private prompts or unrelated proprietary
context.

This matters more than usual here. A plausible-looking recognizer that silently misses a real
identifier is worse than no recognizer, because it produces confidence without coverage.

## Review and acceptance

Keep each pull request focused, and explain in the description:

1. the user or operator problem;
2. the chosen behavior and the alternatives you considered;
3. the tests or evidence you added, with the commands you ran and what they printed;
4. compatibility, privacy, and security impact;
5. documentation, translation, or migration work required, or why none is needed.

Reviewers evaluate, as applicable:

- correctness, offset handling, and input validation;
- the fail-closed, tenancy, vault-scope, and audit boundaries;
- whether detection changes are supported by benchmark evidence rather than intuition;
- compatibility of public schemas, error codes, and placeholder formats;
- supply-chain and dependency risk;
- English and Turkish parity; and
- whether the claims made are narrower than the evidence provided.

Passing CI is required but does not replace review. Maintainers may ask for a smaller change,
additional evidence, or a decision record in `docs/adr/` for anything difficult to reverse. Merge
rules, decision classes, and the role ladder are defined in [GOVERNANCE.md](GOVERNANCE.md).

Maintainers may adjust commit structure during merge while preserving attribution and sign-offs.
Public packages and images are released only through the repository workflows; never publish them
manually from a contributor account.
