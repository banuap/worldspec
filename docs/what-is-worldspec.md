# What is WorldSpec?

**WorldSpec is a declarative language and compiler for describing a software
system — in any language or product — as a set of facts that can be checked
before you change anything.**

Instead of documenting a system in prose that drifts out of date, you describe
it in six precise constructs. The compiler then validates that description and
turns it into a governed package (`.wspkg`) that humans, AI agents, and
(soon) a simulation runtime can all reason over. The core question WorldSpec
exists to answer is:

> *If I make this change, what rule might it break — and how do I get there
> safely?*

WorldSpec is **technology-agnostic**. The same constructs model a mainframe
batch suite, a microservice fleet, a database platform, or a cloud
re-platforming. Nothing in the language is tied to a particular stack.

---

## The six constructs

A WorldSpec model is built from exactly six kinds of statement:

| Construct        | Answers the question…                                  |
|------------------|--------------------------------------------------------|
| **entity**       | What *things* exist? (their stable, descriptive facts) |
| **relationship** | How are those things connected?                        |
| **state**        | What about a thing *changes* over time?                |
| **invariant**    | What rule must *always* hold true?                     |
| **action**       | What change is *permitted*, and how is it undone?      |
| **transition**   | What bigger move am I making, and what must it preserve?|

The split between `entity` (static identity) and `state` (what changes) is the
key modeling idea: invariants and actions reason over **state**, so the things
that can break are exactly the things you've named as mutable.

---

## An example representation

Here is a complete, valid WorldSpec model. It describes a tiny estate — two
services and a shared datastore — and the one rule that must never break during
a platform cutover: **only one service may hold write authority at a time**
(no dual-write). This model compiles with `0` errors and `0` warnings.

```yaml
# entity — the things that exist, and their stable facts
entity Service:
  description: A deployable software service (any language or runtime)
  identity: [serviceId]
  properties:
    serviceId: { type: string, required: true }
    name:      { type: string, required: true }
    platform:  { type: enum, values: [legacy, target] }

entity Datastore:
  description: A store of record the services read and write
  identity: [datastoreId]
  properties:
    datastoreId: { type: string, required: true }
    name:        { type: string, required: true }

# relationship — how the things connect
relationship writes:
  from: Service
  to: Datastore
  cardinality: many

# state — what changes about a Datastore over time
state DatastoreState:
  entity: Datastore
  dimensions:
    writeAuthority: { type: ref, target: Service }
    activeWriters:  { type: int }

# invariant — the rule that must always hold (no dual-write)
invariant SingleWriter:
  appliesTo: Datastore
  expression:
    operator: "<="
    left: { function: count, path: activeWriters }
    right: 1
  severity: critical
  onViolation:
    action: block_transition

# action — a permitted change, with how to roll it back
action TransferWriteAuthority:
  inputs:
    datastore: { type: ref, target: Datastore }
    source:    { type: ref, target: Service }
    target:    { type: ref, target: Service }
  preconditions:
    - datastore.activeWriters == 1
  effects:
    - datastore.writeAuthority = target
  rollback:
    - datastore.writeAuthority = source

# transition — the bigger move, and the invariants it must preserve
transition PlatformCutover:
  action: TransferWriteAuthority
  from: { platform: legacy }
  to:   { platform: target }
  preserves:
    - SingleWriter
```

### Reading the model

- **Entities** `Service` and `Datastore` are the nouns. Their `properties` are
  facts that don't change as the system runs (a service's id, its name).
- The **relationship** `writes` records that services write to datastores —
  the place a dual-write risk would live.
- **State** `DatastoreState` separates the things that *do* change:
  `writeAuthority` (which service owns writes) and `activeWriters` (how many
  are writing right now).
- The **invariant** `SingleWriter` says `count(activeWriters) <= 1` must always
  be true, and that violating it should **block** any transition.
- The **action** `TransferWriteAuthority` is the only sanctioned way to move
  write ownership — and because it declares a `rollback`, it is reversible.
- The **transition** `PlatformCutover` is the migration itself; it explicitly
  **preserves** `SingleWriter`, so the compiler records that this rule must
  hold across the move.

---

## What you get out of it

Run the model through the compiler:

```bash
worldspec validate model/          # check it
worldspec compile  model/ --output build/model.wspkg
```

and you get:

1. **Validation** — every reference, type, enum, and invariant name is checked,
   with stable diagnostic codes (`WS-SYN-*`, `WS-SEM-*`) and line numbers. A
   typo'd invariant name fails the build, so the model can't silently drift.
2. **A `.wspkg`** — a portable package containing the canonical JSON IR plus a
   JSON Schema per entity. Downstream tools depend on this stable contract,
   never on the raw YAML.
3. **(Coming in the runtime milestone)** the ability to load real instances,
   set a state that violates `SingleWriter`, and have the engine *detect* the
   violation and recommend a safer, rollback-protected trajectory.

---

## Where to go next

- **Author your own model:** `docs/usage.md` — a step-by-step guide for turning
  a real codebase (any stack) into a validated model.
- **Full grammar:** `docs/language-spec-v0.1.md`.
- **A larger worked example:** `docs/demo-scenario.md` and
  `models/application-modernization/` — a COBOL/JCL/VSAM → Java cutover.
- **Why it's built this way:** `docs/architecture.md` and `docs/adr/`.
