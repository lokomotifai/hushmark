# Support

Hushmark is community-maintained open-source software provided under the Apache License 2.0,
without warranty, a service-level agreement, or an entitlement to individual support.

## Choose the right route

| Need                    | Route                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Reproducible bug        | [Bug report](https://github.com/lokomotifai/hushmark/issues/new?template=bug.yml)                                         |
| Documentation problem   | [Documentation issue](https://github.com/lokomotifai/hushmark/issues/new?template=documentation.yml)                      |
| Usage question          | [Question](https://github.com/lokomotifai/hushmark/issues/new?template=question.yml)                                      |
| Feature or API proposal | [Feature request](https://github.com/lokomotifai/hushmark/issues/new?template=feature.yml)                                |
| Security vulnerability  | [Private vulnerability reporting](https://github.com/lokomotifai/hushmark/security/advisories/new) — never a public issue |
| Conduct incident        | Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)                                                                           |

Search existing issues and the [documentation](docs/) before opening a new report. Detection quality
questions are usually answered by the [engine comparison](docs/benchmark-comparison.md) and the
[model card](docs/model-card-hushmark-tr.md), which state what has and has not been measured.

## What makes a useful support request

Include the Hushmark version or image digest, which components are running (core, gateway,
enterprise gateway, console), the model backend (`torch`, `onnx`, or none), the deployment profile
(Compose evaluation, single-host production, Helm, air-gap), and the runtime versions of Node.js,
Python, and Docker. State what you expected, what happened, and the smallest reproduction you can
share.

Say whether the problem involves detection quality, masking or restoration, streaming, policy
evaluation, tenancy, the vault, the audit chain, licensing, or deployment. Those paths have
different owners and different diagnostics.

**Sanitize before you post.** Never include real personal data, customer text, resolved placeholder
values, credentials, gateway or admin keys, license issuer keys, audit exports, or non-public logs.
Reproduce the problem with synthetic Turkish data instead: the test corpus in `bench/data/` and the
generators in `bench/` exist for exactly this, and a synthetic reproduction is more useful to a
maintainer than a redacted real one. If a defect only appears on data you cannot share, describe its
shape—length, script, encoding, entity types, surrounding format—rather than the data itself.

For a detection complaint, the most useful report is the input text, the entities you expected with
their offsets, and what the engine actually returned. `POST /v1/analyze` gives you that directly.

## Support boundary

Maintainers can help distinguish a Hushmark defect from a configuration or integration problem, but
cannot operate, tune, or audit your deployment. Support does not cover writing your organization's
policy, assessing your KVKK obligations, provider availability or terms, third-party SDK behavior,
cloud billing, key management operations, production incident command, or a security guarantee for a
deployment nobody has evaluated.

The project cannot give legal advice. Whether a particular masking configuration satisfies a
particular obligation is a question for your own legal and data-protection function; Hushmark
provides a technical control and the evidence of what it did.

Issues may be closed when they lack enough information to reproduce, duplicate an existing report,
concern unsupported behavior, or turn into open-ended consulting. A closure should say why and, when
known, point to the next useful route.

There is no guaranteed response time. Paid support, if offered separately, does not change public
issue priority, review standards, or governance rights.
