# ADR-003 — Separate the compiler from the runtime

**Status:** Accepted

**Context.** The compiler (parse/validate/IR) and the runtime (state, engines,
APIs) have different dependencies and lifecycles, and the runtime is a later
milestone.

**Decision.** Keep the compiler self-contained under `src/worldspec/compiler/`
with no dependency on any runtime, persistence, or web framework. The runtime,
when built, will consume the compiled IR/`.wspkg` only.

**Consequences.** The compiler installs and tests with just `pydantic`,
`PyYAML`, and `typer`. Graph-store and persistence code (Neo4j, PostgreSQL) stay
behind future repository interfaces (instructions operating rule 10) and never
leak into compilation.
