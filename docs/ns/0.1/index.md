---
title: WorldSpec Namespace 0.1
---

# WorldSpec Namespace 0.1

**Namespace URI:** `https://banuap.github.io/worldspec/ns/0.1#`

This document is the human-readable description of the WorldSpec 0.1 namespace.
It enumerates the reserved terms of the language — the construct keywords, the
type vocabulary, and the controlled value sets — that are defined normatively
by the [WorldSpec Language Specification 0.1](../../spec/0.1/). A term is
referenced by appending it to the namespace URI as a fragment, e.g.
`https://banuap.github.io/worldspec/ns/0.1#invariant`.

> WorldSpec 0.1 has a *fixed* set of reserved terms (below). The vocabulary a
> modeler defines — their entities, relationships, states, invariants, actions,
> and transitions — are **instances** of these terms, not part of the
> namespace. The language imposes no domain vocabulary of its own.

## Construct keywords

| Term | Fragment | Definition |
|------|----------|------------|
| entity | `#entity` | A thing that exists, with stable identity and properties. |
| relationship | `#relationship` | A typed, directed association between two entities. |
| state | `#state` | The mutable dimensions of an entity. |
| invariant | `#invariant` | A boolean rule that must hold over an entity. |
| action | `#action` | A permitted change with preconditions, effects, rollback. |
| transition | `#transition` | A move that applies an action and preserves invariants. |

## Type vocabulary

`#string` · `#int` · `#float` · `#bool` · `#enum` · `#ref` · `#datetime`

See [specification §4](../../spec/0.1/#4-type-system) for the meaning and the
extra fields required by `enum` (`values`) and `ref` (`target`).

## Controlled value sets

| Facet | Fragment | Allowed values |
|-------|----------|----------------|
| Invariant severity | `#severity` | `info`, `warning`, `high`, `critical` |
| On-violation action | `#onViolation` | `block_transition`, `warn`, `record` |
| Relationship cardinality | `#cardinality` | `one`, `many` |
| Comparison operator | `#cmp-op` | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| Logical operator | `#bool-op` | `and`, `or`, `not` |
| Aggregate function | `#agg-fn` | `count`, `sum`, `min`, `max`, `exists` |

## Versioning

This namespace is immutable for the lifetime of WorldSpec 0.1. A
backward-incompatible change to any reserved term will be published under a new
namespace URI (e.g. `.../ns/0.2#`). See
[`GOVERNANCE.md`](https://github.com/banuap/worldspec/blob/main/GOVERNANCE.md).
