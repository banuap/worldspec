# WorldSpec governance, versioning, and change process

This document governs the **WorldSpec language specification** and its
namespace. It is intentionally lightweight; it will be tightened if and when
the language moves toward a formal standards venue (see `PUBLISHING.md`).

## Artifacts and their licenses

| Artifact | Location | License |
|----------|----------|---------|
| Specification document | `docs/spec/<version>/`, published at `/spec/<version>/` | CC BY 4.0 + royalty-free implementation grant |
| Namespace document | `docs/ns/<version>/`, published at `/ns/<version>/` | CC BY 4.0 |
| Model JSON Schema | `docs/schemas/` | CC BY 4.0 |
| Conformance suite | `conformance/` | CC BY 4.0 |
| Reference implementation (compiler, runtime, CLI, API) | `src/` | AGPL-3.0-or-later |

Anyone may implement the specification without royalty or permission (see the
specification's *Status of This Document*). The copyleft AGPL applies only to
this repository's *implementation code*, never to the language or to
independent implementations.

## Independent version lines

WorldSpec versions three things independently (mirrored in
`pyproject.toml [tool.worldspec.versions]`):

- **language** — the constructs, syntax, type system, and grammars in the spec.
- **compiler** — the reference implementation's behavior.
- **package format** — the `.wspkg` / canonical-IR layout (`irVersion`).

Each follows **semantic versioning** within its own line.

## What counts as a breaking change (language)

A change is **breaking** (requires a new `MAJOR`/minor namespace) if it can turn
a previously-conforming model into a non-conforming one, or change the meaning
of an existing construct, type, operator, severity, or diagnostic contract.
Examples: removing or renaming a construct or type; changing a default;
narrowing an allowed value set; repurposing a `WS-*` diagnostic code.

Non-breaking, additive changes (new optional fields, new diagnostic codes, new
aggregate functions that don't alter existing models) may ship in a new MINOR
of the language within the same namespace, clearly marked.

## Namespace stability

A published namespace URI (`/ns/0.1#`) is **immutable**. Reserved terms defined
there never change meaning. A breaking change is published under a new
namespace URI (`/ns/0.2#`, …); the old one remains resolvable forever.

## Specification stability and errata

A published spec version (`/spec/0.1/`) does not change once released, except
for **errata**: clarifications and typo fixes that do not alter conformance.
Errata are listed at the bottom of the affected spec document with a date.
Substantive changes produce a new spec version.

## Change process

1. Open an issue at `https://github.com/banuap/worldspec/issues` describing the
   problem and the proposed change (a **WorldSpec Change Proposal**).
2. Changes that affect conformance MUST include: the motivation, the spec
   edits, and additions to the `conformance/` suite (valid and/or invalid
   cases) demonstrating the new behavior.
3. The reference implementation and the conformance suite MUST be updated in
   the same change set as the spec text, so the three stay in lockstep.
4. Maintainers merge after review. Until a wider governing body exists, the
   repository maintainers are the editors of record.

## Conformance and the test suite

The machine-checkable conformance criteria live in `conformance/` and are the
authority for "does X conform". Implementations are encouraged to run the suite
and report results. See `conformance/README.md`.
