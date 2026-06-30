---
title: WorldSpec
---

# WorldSpec

**A declarative language for modeling software systems — in any language or
product — as entities, relationships, states, invariants, actions, and
transitions, so that proposed changes can be checked against critical
invariants *before* execution.**

WorldSpec is technology-agnostic: the same six constructs model a mainframe
batch suite, a microservice fleet, a database platform, or a cloud
re-platforming.

## The specification

| | |
|---|---|
| **Latest version** | [`/spec/`](spec/) |
| **This version (0.1)** | [`/spec/0.1/`](spec/0.1/) |
| **Namespace (0.1)** | `https://banuap.github.io/worldspec/ns/0.1#` — see [`/ns/0.1/`](ns/0.1/) |
| **Model JSON Schema (0.1)** | [`worldspec-model-0.1.schema.json`](schemas/worldspec-model-0.1.schema.json) |
| **Status** | Draft Community Specification |
| **Spec license** | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) + a royalty-free implementation grant |

## Learn

- [What is WorldSpec?](what-is-worldspec) — the language in five minutes, with a complete example.
- [Language specification v0.1](spec/0.1/) — the normative reference (syntax, semantics, grammar, conformance).
- [Authoring guide](usage) — turn a real codebase into a validated model.
- Worked examples: [COBOL → Java cutover](demo-scenario) · [securities-lending rebate](example-short-interest-rebate).

## Implement

WorldSpec is **free to implement**. The reference implementation (compiler,
runtime, CLI, REST API) lives at
[github.com/banuap/worldspec](https://github.com/banuap/worldspec) under the
AGPL-3.0; the *specification itself* is published under CC BY 4.0 with an
explicit, royalty-free grant to build conforming tools (see the spec's
*Status of This Document*). A [conformance test suite](https://github.com/banuap/worldspec/tree/main/conformance)
lets independent implementations check themselves.

## Cite

See [`CITATION.cff`](https://github.com/banuap/worldspec/blob/main/CITATION.cff)
in the repository (a DOI is minted per release via Zenodo).
