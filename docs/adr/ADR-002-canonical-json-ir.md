# ADR-002 — Use a canonical JSON IR

**Status:** Accepted

**Context.** Multiple consumers (runtime, schema/graph generators, future ML)
need a stable representation that is decoupled from the authoring syntax.

**Decision.** Compile every construct into a neutral, JSON-serializable object
with a `kind` discriminator. The whole model compiles to
`{ irVersion, model, constructs: [...] }`. The (future) runtime and all
generators depend on this IR, never on raw YAML.

**Consequences.** The authoring format can evolve (ADR-001) without breaking
downstream consumers as long as the IR is preserved or versioned (`irVersion`).
The IR is the contract tested by `tests/test_compile_and_package.py`.
