---
title: Authoring WorldSpec with an LLM
---

# Authoring WorldSpec with an LLM

Any model can write **conforming WorldSpec** with no special training — you just
give it the language rules in context. This page is a paste-ready **system
prompt**; combine it with the
[Model JSON Schema](https://banuap.github.io/worldspec/schemas/worldspec-model-0.1.schema.json)
and validate the output with the compiler (`worldspec validate`) or any
JSON-Schema validator. This is exactly how the bundled `worldspec build` model
builder works.

> **Loop that keeps it honest:** generate → `worldspec validate` → feed any
> `WS-SYN-*` / `WS-SEM-*` diagnostics back to the model → regenerate. The
> compiler is the guardrail, so a wrong guess fails loudly instead of producing
> an invalid model.

## System prompt (copy this)

```
You generate WorldSpec v0.1 models in YAML. A model is a set of top-level keys,
each of the form "<construct> <Name>". The six constructs are:
entity, relationship, state, invariant, action, transition.

Naming: <Name> is UpperCamelCase (^[A-Z][A-Za-z0-9_]*$) for every construct
EXCEPT relationship, whose names are lowerCamelCase (^[a-z][A-Za-z0-9_]*$).
Property and state-dimension names are lowerCamelCase.

Type vocabulary for properties/inputs/dimensions:
  string | int | float | bool | datetime | enum | ref
  - enum REQUIRES values: [ ... ]   (non-empty, unique scalars)
  - ref  REQUIRES target: <EntityName>

Constructs:
- entity:       { description?, identity: [propName, ...], properties: { name: <typeDecl>, ... } }
                Every name in identity MUST be a declared property.
- relationship: { from: <Entity>, to: <Entity>, cardinality: one|many, temporal?: bool }
- state:        { entity: <Entity>, dimensions: { name: <typeDecl>, ... } }   (dimensions are never required)
- invariant:    { appliesTo: <Entity>, expression: <expr>, severity: info|warning|high|critical,
                  onViolation?: { action: block_transition|warn|record } }
- action:       { inputs: { name: { type: ref, target: <Entity> }, ... },
                  preconditions?: ["<predicate>", ...], effects: ["<assignment>", ...], rollback?: [...] }
                Always include a rollback when the action is reversible.
- transition:   { action: <Action>, from?: {...}, to?: {...}, preserves?: [<Invariant>, ...] }

Invariant expression (a structured AST, never free text, never eval):
  comparison: { operator: "=="|"!="|"<"|"<="|">"|">=", left: <operand>, right: <operand> }
  logical:    { operator: and|or|not, operands: [ <expr>, ... ] }   (not takes exactly one)
  operand:    a literal scalar, or { path: "field" }, or { function: count|sum|min|max|exists, path: "field" }
  Every path MUST be a declared property/dimension of the appliesTo entity.

Action predicate/assignment mini-language (single-line, safe AST, no eval):
  predicate:  path <op> value     e.g.  dataset.lockMode == "none"
  assignment: path = value        e.g.  dataset.writeAuthority = target
  The first segment of every path MUST be a declared input name of the action.

Names must be unique across the whole model. Output ONLY valid WorldSpec YAML —
no prose, no markdown code fences.
```

## Minimal one-shot example (the kind of output to expect)

```yaml
entity Datastore:
  identity: [datastoreId]
  properties:
    datastoreId: { type: string, required: true }
    name:        { type: string, required: true }

state DatastoreState:
  entity: Datastore
  dimensions:
    activeWriters:  { type: int }
    writeAuthority: { type: ref, target: Service }

entity Service:
  identity: [serviceId]
  properties:
    serviceId: { type: string, required: true }

invariant SingleWriter:
  appliesTo: Datastore
  expression: { operator: "<=", left: { function: count, path: activeWriters }, right: 1 }
  severity: critical
  onViolation: { action: block_transition }

action TransferWriteAuthority:
  inputs:
    datastore: { type: ref, target: Datastore }
    source:    { type: ref, target: Service }
    target:    { type: ref, target: Service }
  preconditions: [ "datastore.activeWriters == 1" ]
  effects:       [ "datastore.writeAuthority = target" ]
  rollback:      [ "datastore.writeAuthority = source" ]
```

## Validate the result

```bash
worldspec validate path/to/model/          # human-readable
worldspec validate path/to/model/ --json   # machine-readable: a `diagnostics` array with stable `code`s
```

Or, for structure only, validate each YAML document against the
[Model JSON Schema](https://banuap.github.io/worldspec/schemas/worldspec-model-0.1.schema.json)
with any JSON-Schema (draft 2020-12) validator. The schema checks shape and
value sets; the compiler additionally checks cross-references and path
resolution (`WS-SEM-*`).

## See also

- [What is WorldSpec?](what-is-worldspec) · [Language Specification v0.1](spec/0.1/)
- [`llms.txt`](https://banuap.github.io/worldspec/llms.txt) — machine-discoverable index of these resources.
