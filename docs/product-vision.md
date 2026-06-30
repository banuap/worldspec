# WorldSpec product vision

**WorldSpec is a declarative language and runtime for modeling enterprise
entities, relationships, states, invariants, actions, and transitions. It gives
humans, AI agents, causal models, and world models a shared, governed
representation of the enterprise and allows proposed actions to be simulated
before execution.**

> Model the enterprise. Predict the transition. Preserve what matters.

WorldSpec is **not** another agent framework. It is the enterprise semantic and
state-transition foundation that agents and models use to understand: what
exists, how it is related, what state it is in, what actions are permitted, what
must remain invariant, and what consequences follow from a proposed change.

## Lifecycle

```
Observe current system
  -> represent system state
  -> define proposed action
  -> evaluate invariants
  -> simulate transition
  -> explain consequences
  -> recommend safer trajectory
  -> capture observed outcome
  -> learn from prediction error
```

## Scope: any language, any software product

WorldSpec is **technology-agnostic**. The six constructs — entity,
relationship, state, invariant, action, transition — describe *any* software
system regardless of its implementation language, runtime, or vintage: a
mainframe batch suite, a microservice fleet, a database platform, a packaged
product, a cloud re-platforming, or a mixed legacy-and-modern portfolio. If
there are things that exist, rules that must hold, and risky changes to make,
WorldSpec can represent and simulate them.

## First worked example

The bundled example is application-modernization and cutover assurance — a
COBOL/JCL/VSAM → Java transition (see `demo-scenario.md`), chosen as one
concrete, high-stakes illustration. It is an *example, not a limit*: the same
language models a Java→Kotlin migration, a database cutover, or an API
deprecation just as well. We deliver a narrow, working vertical slice first —
not a generalized ontology platform — and the modeling language stays neutral.

## Where we are

Milestone 1 (language + compiler) is implemented. Milestones 2–4 (runtime,
demo, Studio) and the ML/JEPA roadmap follow, in that order, only after the
prior milestone works from a clean checkout.
