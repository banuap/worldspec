# WorldSpec Language Specification — v0.1

> Status: Draft / implemented in the v0.1 compiler.
> Authoring format: **YAML**. The runtime depends on the compiled **canonical IR**, never on raw YAML (ADR-002).

WorldSpec models an enterprise estate as six core constructs:

```
entity  relationship  state  invariant  action  transition
```

A WorldSpec **model** is a directory of one or more `.yaml` / `.yml` files. All
files in the directory are merged into a single namespace before validation, so
construct names must be unique across the whole model.

---

## 1. File shape

Each top-level mapping key has the form `"<construct> <Name>"`:

```yaml
entity Application:
  description: A deployable enterprise software system
```

- `<construct>` is one of the six keywords above (lower-case).
- `<Name>` is `UpperCamelCase` (`^[A-Z][A-Za-z0-9_]*$`) for every construct
  **except `relationship`**, whose names are `lowerCamelCase`
  (`^[a-z][A-Za-z0-9_]*$`, e.g. `dependsOn`, `reads`, `writes`).
- The body is a mapping whose shape depends on the construct.

Any other top-level key, an unknown construct keyword, or a malformed key
produces a syntax diagnostic (`WS-SYN-*`).

---

## 2. Type system

Property and dimension declarations use a small closed type vocabulary:

| `type`    | Meaning                                   | Extra fields            |
|-----------|-------------------------------------------|-------------------------|
| `string`  | UTF-8 text                                | —                       |
| `int`     | Integer                                   | —                       |
| `float`   | Floating point number                     | —                       |
| `bool`    | Boolean                                   | —                       |
| `enum`    | One value drawn from a fixed list         | `values: [...]` (req.)  |
| `ref`     | Reference to an entity instance           | `target: <EntityName>`  |
| `datetime`| ISO-8601 timestamp                        | —                       |

`enum` **must** declare a non-empty `values` list of unique scalars.
`ref` **must** declare a `target` naming a declared entity (checked
semantically).

---

## 3. Constructs

### 3.1 `entity`

```yaml
entity Application:
  description: A deployable enterprise software system
  identity:
    - applicationId
  properties:
    applicationId: { type: string, required: true }
    name:          { type: string, required: true }
    criticality:   { type: enum, values: [low, medium, high, systemic] }
    lifecycle:     { type: enum, values: [active, modernizing, retiring] }
```

- `identity` (required, non-empty): list of property names forming the entity key.
- `properties` (required): map of property name → property declaration.
- Every name in `identity` must be a declared property (semantic check).
- Property names are `lowerCamelCase`: `^[a-z][A-Za-z0-9_]*$`.

### 3.2 `relationship`

```yaml
relationship dependsOn:
  from: Application
  to: Application
  cardinality: many
  temporal: true
```

- `from`, `to` (required): names of declared entities.
- `cardinality` (required): `one` or `many`.
- `temporal` (optional, default `false`): whether the edge carries valid-time.
- Relationship names are `lowerCamelCase`.

### 3.3 `state`

```yaml
state DatasetState:
  entity: Dataset
  dimensions:
    availability:   { type: enum, values: [available, unavailable] }
    lockMode:       { type: enum, values: [none, shared, exclusive] }
    writeAuthority: { type: ref, target: Application }
```

- `entity` (required): the declared entity this state describes.
- `dimensions` (required): map of dimension name → declaration (same type
  vocabulary as properties; dimensions are never `required`).

### 3.4 `invariant`

```yaml
invariant SingleWriter:
  appliesTo: Dataset
  expression:
    operator: "<="
    left: { function: count, path: activeWriters }
    right: 1
  severity: critical
  onViolation:
    action: block_transition
```

- `appliesTo` (required): a declared entity.
- `expression` (required): a structured boolean expression (see §4).
- `severity` (required): `info` | `warning` | `high` | `critical`.
- `onViolation.action` (optional): `block_transition` | `warn` | `record`
  (default `warn`).

### 3.5 `action`

```yaml
action TransferWriteAuthority:
  inputs:
    dataset: { type: ref, target: Dataset }
    source:  { type: ref, target: Application }
    target:  { type: ref, target: Application }
  preconditions:
    - target.validationStatus == "passed"
    - dataset.lockMode == "none"
  effects:
    - dataset.writeAuthority = target
  rollback:
    - dataset.writeAuthority = source
```

- `inputs` (required): map of input name → typed declaration (typically `ref`).
- `preconditions` (optional): list of **predicate** strings (see §5).
- `effects` (required, non-empty): list of **assignment** strings (see §5).
- `rollback` (optional): list of assignment strings. If absent, the action is
  flagged as irreversible during compilation (warning), per operating rule 17.

### 3.6 `transition`

```yaml
transition COBOLToJava:
  action: TransferWriteAuthority
  from: { orchestrationPlatform: COBOL }
  to:   { orchestrationPlatform: Java }
  preserves:
    - SingleWriter
    - SettlementBalance
```

- `action` (required): a declared action.
- `from`, `to` (optional): free-form context maps describing the world before /
  after the transition.
- `preserves` (optional): list of declared invariant names that must hold across
  the transition.

---

## 4. Invariant expressions

Invariant expressions are a structured (already-parsed) AST — they are authored
as nested mappings, never as free text, so no string parsing or `eval` is
involved (ADR-005, security rule).

```
expression := comparison | logical
comparison := { operator: <cmp>, left: operand, right: operand }
logical    := { operator: <bool>, operands: [ expression, ... ] }
operand    := literal | path-ref | aggregate
literal    := <scalar>                       # number, string, bool
path-ref   := { path: "<dotted.path>" }
aggregate  := { function: <fn>, path: "<dotted.path>" }
```

- `<cmp>` ∈ `==`, `!=`, `<`, `<=`, `>`, `>=`
- `<bool>` ∈ `and`, `or`, `not` (`not` takes exactly one operand)
- `<fn>` ∈ `count`, `sum`, `min`, `max`, `exists`

A bare scalar on `left`/`right` is a literal; a mapping with `path` is a
reference; a mapping with `function` + `path` is an aggregate.

---

## 5. Action predicate / assignment mini-language

Preconditions and effects are short single-line expressions parsed into a safe
AST. **No Python `eval` is ever used.**

```
predicate  := path <cmp> operand          # e.g.  dataset.lockMode == "none"
assignment := path "=" operand            # e.g.  dataset.writeAuthority = target
operand    := path | string | number | bool
path       := IDENT ("." IDENT)*
```

- `<cmp>` ∈ `==`, `!=`, `<`, `<=`, `>`, `>=`
- Strings may be double- or single-quoted. `true`/`false` are booleans. Numbers
  are int/float.
- The leading identifier of a `path` in an action body must resolve to one of
  the action's declared `inputs` (semantic check).

---

## 6. Canonical IR

Every construct compiles to a neutral JSON object with a `kind` discriminator
(`entity`, `relationship`, `state`, `invariant`, `action`, `transition`). The
whole model compiles to:

```json
{
  "irVersion": "0.1.0",
  "model": "<name>",
  "constructs": [ { "kind": "...", "name": "...", ... }, ... ]
}
```

See `worldspec compile --emit ir` and the generated `ontology.json` inside a
`.wspkg`.

---

## 7. Diagnostics

Diagnostics carry a stable code, message, source file, line (best effort), and
an optional suggestion. Codes:

- `WS-SYN-####` — syntax / structural errors (bad key, missing required field,
  bad type, malformed expression).
- `WS-SEM-####` — semantic errors (unknown reference, duplicate name, dangling
  invariant in a transition, identity property not declared, …).

A non-empty set of `error`-severity diagnostics fails `validate` and `compile`
with a non-zero exit code.
