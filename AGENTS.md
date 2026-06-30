# AGENTS.md — operating rules for WorldSpec development

This file is the contract any human or AI agent must follow when changing this
repository. It restates the operating rules from
`WORLDSPEC_AGENT_INSTRUCTIONS.md` §18 and records how this build honours them.

## Read first

1. Read `WORLDSPEC_AGENT_INSTRUCTIONS.md` (the mission) and
   `docs/language-spec-v0.1.md` (the implemented language).
2. Inspect the existing code before adding files. The compiler is
   `src/worldspec/compiler/`; keep compiler and runtime independent (ADR-003).

## Hard rules

- **No `eval`.** Invariant expressions and action predicates/effects are parsed
  into a safe AST (`compiler/parser`, `compiler/ast`). See ADR-005.
- **Reject silent failure.** Every problem is a `Diagnostic` with a stable code
  (`WS-SYN-*` / `WS-SEM-*`), a file, a best-effort line, and a suggestion.
- **Never hard-code the demo ontology into the compiler/runtime.** The
  `application-modernization` model lives only in `models/`.
- **The runtime depends on the IR, not raw YAML** (ADR-002).
- **Smallest end-to-end increment.** No speculative abstractions; defer
  generators/runtime features until something consumes them (recorded in
  `docs/open-questions.md`).
- **Tests before "done".** Each feature needs unit, semantic, and at least one
  negative test. Compiler coverage target ≥ 90%.
- **Determinism in tests.** No clocks/network in compiler code paths.
- **No secrets** in code or examples.
- **No autonomous execution in v0.1.** `deploy`/`simulate` are honest stubs.

## Current scope

Implemented: language v0.1, parser, validators, IR, generators, CLI
(`validate`/`compile`/`inspect`/`init`/`simulate`/`serve`/`demo`); the runtime
(registry, entity/relationship/state services, invariant/action/transition
engines, evidence); the REST API + Studio; two demo models; tests.

Deferred (deliberately): persistent runtime/store, Studio polish, ML/JEPA. See
`docs/open-questions.md`. Keep the API thin (logic in `api/service.py`); keep the
runtime dependent only on the IR.

## Definition of done (instructions §21)

A change is done only when: implementation complete, tests pass, docs updated,
errors are actionable, no secrets committed, and acceptance commands work from a
clean checkout (`worldspec validate` + `worldspec compile` on the demo model).
