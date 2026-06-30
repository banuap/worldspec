---
title: WorldSpec Language Specification 0.1
---

# WorldSpec Language Specification

## Version 0.1 — Draft Community Specification

| | |
|---|---|
| **This version** | `https://banuap.github.io/worldspec/spec/0.1/` |
| **Latest version** | `https://banuap.github.io/worldspec/spec/` |
| **Namespace** | `https://banuap.github.io/worldspec/ns/0.1#` |
| **Model JSON Schema** | `https://banuap.github.io/worldspec/schemas/worldspec-model-0.1.schema.json` |
| **Editors** | The WorldSpec Project (`github.com/banuap/worldspec`) |
| **Date** | 30 June 2026 |
| **Spec license** | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) + royalty-free implementation grant (see §[Status](#status-of-this-document)) |

---

## Abstract

**WorldSpec** is a declarative language for describing a software system as a
set of facts that can be validated and reasoned over before the system is
changed. A WorldSpec *model* describes a system using six constructs —
**entity, relationship, state, invariant, action,** and **transition** — and
compiles to a neutral, machine-readable intermediate representation (the
*canonical IR*). The language is technology-agnostic: it imposes no fixed
vocabulary and is not tied to any implementation language, runtime, or
persistence technology. This document specifies the syntax, the type system,
the invariant- and action-expression grammars, the canonical IR, the
diagnostic model, and the conformance requirements for WorldSpec 0.1.

## Status of This Document

This is a **Draft Community Specification** published by the WorldSpec Project.
It is not a standard of any formal standards body. It is a stable, citable
snapshot intended for implementation and review; feedback is collected as
issues at `https://github.com/banuap/worldspec`.

The reference implementation (compiler, runtime, CLI, and REST API) is
distributed separately under the GNU AGPL-3.0. **This specification document**
is licensed under [Creative Commons Attribution 4.0 International (CC BY
4.0)](https://creativecommons.org/licenses/by/4.0/).

**Implementation grant.** Anyone may implement this specification, in whole or
in part, for any purpose, without royalty and without seeking permission. No
patent or trademark rights are granted by implication. Implementations are
encouraged — but not required — to indicate the specification version they
target and to publish their results against the conformance suite (§10).

## Conformance

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**,
**SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this
document are to be interpreted as described in [BCP 14] ([RFC 2119], [RFC 8174])
when, and only when, they appear in all capitals.

This document defines three conformance classes; their detailed criteria are in
§10:

- a **conforming model** — a set of WorldSpec source documents that satisfies
  all syntactic and semantic requirements of this specification;
- a **conforming validator** (compiler front end) — a tool that accepts
  conforming models, rejects non-conforming ones, and reports the required
  diagnostics;
- a **conforming IR consumer** — a tool that reads the canonical IR (§8) and
  preserves its meaning.

---

## 1. Introduction

A WorldSpec **model** is a directory of one or more `.yaml` / `.yml` documents.
All documents in the directory are merged into a single namespace before
validation; construct names therefore **MUST** be unique across the whole model.
The authoring surface syntax is YAML; conforming consumers depend on the
compiled canonical IR (§8), **never** on the raw YAML.

## 2. Constructs

A model is built from exactly six construct kinds:

| Construct | Purpose |
|-----------|---------|
| `entity` | A thing that exists, with stable identity and descriptive properties. |
| `relationship` | A typed, directed association between two entities. |
| `state` | The mutable dimensions of an entity that change over its lifecycle. |
| `invariant` | A boolean rule over an entity's properties/state that MUST hold. |
| `action` | A permitted change, with preconditions, effects, and optional rollback. |
| `transition` | A larger move that applies an action and declares preserved invariants. |

## 3. Document and naming rules

Each top-level mapping key **MUST** have the form `"<construct> <Name>"`.

- `<construct>` **MUST** be one of the six lower-case keywords in §2.
- `<Name>` **MUST** match `^[A-Z][A-Za-z0-9_]*$` (UpperCamelCase) for every
  construct **except** `relationship`, whose names **MUST** match
  `^[a-z][A-Za-z0-9_]*$` (lowerCamelCase).
- Property and state-dimension names **MUST** match `^[a-z][A-Za-z0-9_]*$`.

A top-level key that is malformed, names an unknown construct, or has a bad
name case **MUST** produce a `WS-SYN-*` diagnostic (§9).

## 4. Type system

Property and dimension declarations use a closed type vocabulary:

| `type` | Meaning | Extra fields |
|--------|---------|--------------|
| `string` | UTF-8 text | — |
| `int` | Integer | — |
| `float` | Floating-point number | — |
| `bool` | Boolean | — |
| `enum` | One value from a fixed list | `values: [...]` (REQUIRED, non-empty, unique scalars) |
| `ref` | Reference to an entity instance | `target: <EntityName>` (REQUIRED; MUST name a declared entity) |
| `datetime` | ISO-8601 timestamp | — |

## 5. Construct definitions

The normative shape of each construct (required and optional fields) is as
given in the reference grammar below and in the [Model JSON
Schema](https://banuap.github.io/worldspec/schemas/worldspec-model-0.1.schema.json),
which is normative for document structure. A summary:

- **entity** — `identity` (REQUIRED, non-empty list of declared property names),
  `properties` (REQUIRED map), optional `description`.
- **relationship** — `from`, `to` (REQUIRED declared entities), `cardinality`
  (REQUIRED, `one` | `many`), optional `temporal` (default `false`).
- **state** — `entity` (REQUIRED declared entity), `dimensions` (REQUIRED map;
  dimensions are never `required`).
- **invariant** — `appliesTo` (REQUIRED declared entity), `expression`
  (REQUIRED, §6), `severity` (REQUIRED, `info` | `warning` | `high` |
  `critical`), optional `onViolation.action` (`block_transition` | `warn` |
  `record`; default `warn`).
- **action** — `inputs` (REQUIRED map of typed declarations), optional
  `preconditions` (§7), `effects` (REQUIRED, non-empty, §7), optional
  `rollback`. An action without `rollback` is irreversible and **SHOULD** be
  flagged with a warning.
- **transition** — `action` (REQUIRED declared action), optional `from`/`to`
  free-form context maps, optional `preserves` (list of declared invariant
  names).

## 6. Invariant expression grammar

Invariant expressions are a structured, already-parsed AST authored as nested
mappings. No string parsing of expressions and **no `eval`** is permitted in a
conforming validator. In ABNF-style EBNF:

```ebnf
expression  = comparison / logical
comparison  = "{" "operator:" cmp-op "," "left:" operand "," "right:" operand "}"
logical     = "{" "operator:" bool-op "," "operands:" "[" expression *( "," expression ) "]" "}"
operand     = literal / path-ref / aggregate
literal     = number / string / boolean
path-ref    = "{" "path:" dotted-path "}"
aggregate   = "{" "function:" agg-fn "," "path:" dotted-path "}"

cmp-op      = "==" / "!=" / "<" / "<=" / ">" / ">="
bool-op     = "and" / "or" / "not"          ; "not" takes exactly one operand
agg-fn      = "count" / "sum" / "min" / "max" / "exists"
dotted-path = ident *( "." ident )
ident       = ALPHA *( ALPHA / DIGIT / "_" )
```

Every `dotted-path` in an invariant **MUST** resolve to a declared property or
state dimension of the invariant's `appliesTo` entity; a validator **SHOULD**
warn (`WS-SEM-0050`) when it does not.

## 7. Action predicate / assignment grammar

Preconditions and effects are single-line expressions parsed into a safe AST.
**No `eval`** is permitted.

```ebnf
predicate   = path SP cmp-op SP operand        ; e.g.  dataset.lockMode == "none"
assignment  = path SP "=" SP operand           ; e.g.  dataset.writeAuthority = target
operand     = path / string / number / boolean
path        = ident *( "." ident )
cmp-op      = "==" / "!=" / "<" / "<=" / ">" / ">="
```

Strings may be single- or double-quoted; `true`/`false` are booleans; numbers
are int or float. The leading `ident` of any `path` in an action body **MUST**
resolve to one of the action's declared `inputs` (`WS-SEM-0031` otherwise).

## 8. Canonical IR

Every construct compiles to a neutral JSON object carrying a `kind`
discriminator (`entity`, `relationship`, `state`, `invariant`, `action`,
`transition`). The whole model compiles to:

```json
{
  "irVersion": "0.1.0",
  "model": "<name>",
  "constructs": [ { "kind": "...", "name": "...", "...": "..." } ]
}
```

The canonical IR is the **stable contract** between a validator and any
downstream consumer. A conforming IR consumer **MUST** treat the IR as
authoritative and **MUST NOT** require access to the original YAML.

## 9. Diagnostics

Diagnostics carry a stable code, a message, a source file, a best-effort line,
and an optional suggestion.

- `WS-SYN-####` — syntax / structural errors.
- `WS-SEM-####` — semantic errors (unknown reference, duplicate name, dangling
  invariant in a transition, identity property not declared, …).

A non-empty set of `error`-severity diagnostics **MUST** cause validation to
fail. The stable codes are part of this specification's contract; a conforming
validator **SHOULD** emit the code that most precisely matches the defect.

## 10. Conformance classes

**Conforming model.** A set of WorldSpec documents that: uses only the six
constructs; satisfies §3 naming; uses only the §4 types; whose expressions and
action bodies satisfy §6–§7; and that produces **zero** `error`-severity
diagnostics from a conforming validator.

**Conforming validator.** A tool that: accepts every conforming model and
compiles it to canonical IR (§8); rejects every non-conforming model with at
least one `error` diagnostic; never executes model-supplied strings (no
`eval`); and runs semantic validation only after structural parsing succeeds,
so cross-reference diagnostics are never spurious.

**Conforming IR consumer.** A tool that reads canonical IR with `irVersion`
`0.1.x` and preserves the meaning of every construct it reports or acts upon.

The machine-checkable portion of these criteria is exercised by the
[conformance suite](https://github.com/banuap/worldspec/tree/main/conformance):
each `valid/` model MUST compile cleanly, and each `invalid/` model MUST fail
with the documented diagnostic code.

## 11. Media type (provisional)

WorldSpec source documents **SHOULD** use the media type
`application/worldspec+yaml` and the file extensions `.yaml` / `.yml`. The
canonical IR **SHOULD** use `application/worldspec-ir+json`. These media types
are provisional pending registration (see the repository `PUBLISHING.md`).

## References

### Normative

- **[BCP 14]** S. Bradner, *Key words for use in RFCs to Indicate Requirement
  Levels*, [RFC 2119]; B. Leiba, *Ambiguity of Uppercase vs Lowercase in RFC
  2119 Key Words*, [RFC 8174].
- **[YAML]** O. Ben-Kiki et al., *YAML Ain't Markup Language (YAML) 1.2*.
- **[JSON Schema]** *JSON Schema: A Media Type for Describing JSON Documents*,
  draft 2020-12.

### Informative

- WorldSpec reference implementation — `https://github.com/banuap/worldspec`.
- *What is WorldSpec?* — `https://banuap.github.io/worldspec/what-is-worldspec`.

[BCP 14]: https://www.rfc-editor.org/info/bcp14
[RFC 2119]: https://www.rfc-editor.org/rfc/rfc2119
[RFC 8174]: https://www.rfc-editor.org/rfc/rfc8174
