# ADR-0005: Offsets are Unicode code points, end-exclusive, on every surface

- Status: Accepted
- Date: 2026-08-10
- Scope: core, gateway, SDKs, benchmark

## Context

Detection produces spans, and masking replaces text at those spans. The two operations happen in
different languages: Python measures strings in code points, JavaScript in UTF-16 code units.

Turkish text makes the disagreement routine rather than exotic. Characters outside the Basic
Multilingual Plane are rare in Turkish, but any user-supplied text can contain an emoji, and a
single one shifts every subsequent JavaScript index by one relative to Python. An off-by-one in a
masking offset does not raise an error. It leaves a fragment of an identity number in the outgoing
request.

## Decision

All offsets in the public API, the SDKs, the benchmark, and internal interchange are Unicode code
point indices, end-exclusive. The gateway converts at its own boundary rather than propagating
UTF-16 indices inward, and masking replaces spans without normalizing or altering untouched
characters.

The benchmark's strict matching requires identical type and identical code-point offsets, so an
encoding regression shows up as a scored failure rather than as a subtle production bug.

## Alternatives considered

**UTF-16 code units.** Rejected. It is convenient for exactly one of the two runtimes and wrong for
the other, and it makes the Python core's natural representation the special case.

**Byte offsets in UTF-8.** Rejected. They are unambiguous but unreadable in an API response, and
they require both consumers to do arithmetic that neither language does natively.

**Returning the matched substring instead of offsets.** Rejected. It cannot express which occurrence
of a repeated value was matched, and it makes the response carry the original value—precisely what
`/v1/mask` omits by default.

## Consequences

Every new surface that handles spans has to convert at its edge. This is documented in
`docs/api-reference.md` and enforced by tests, including a round-trip property test that masks and
restores generated text.

Text is never normalized as a side effect of masking. Unicode normalization would change offsets
computed against the original input, so the input a caller sends is the input that is measured.

## Security and privacy impact

An offset error is a silent partial disclosure. Making the representation identical across the whole
system removes an entire class of bug that would otherwise be found in production, by someone
reading a provider log.
