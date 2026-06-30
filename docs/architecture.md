# WorldSpec architecture

The target logical architecture (instructions §5) is layered:

```
Experience (CLI | Studio | REST API)
   -> Runtime (Registry | State | Invariants | Actions | Transitions | Evidence)
      -> Compiler (Parser | AST | Validation | IR | Generators)
         -> Persistence (Neo4j | PostgreSQL | pgvector | Object storage)
            -> Source adapters (COBOL | JCL | VSAM | Scheduler | Events)
```

## What this build contains

This repository implements the **Compiler** (`src/worldspec/compiler/`), the
**Runtime** (`src/worldspec/runtime/`), and the **Experience layer**
(`src/worldspec/cli/` + `src/worldspec/api/` with a static Studio). The only
deferred layers are **persistence** (the runtime is in-memory behind repository
interfaces, ADR-004) and the **ML/JEPA** roadmap (ADR-007).

### Runtime (Milestone 2)

The runtime loads the compiled IR and runs three engines over an in-memory world:

```
.wspkg (IR) -> RuntimeModel -> World (entities/relationships/state)
   InvariantEngine  : evaluate the expression AST against state (no eval)
   ActionEngine     : preconditions -> effects on a candidate world -> reversible plan
   TransitionEngine : preserved-invariant checks -> risk -> model-derived trajectory -> evidence
```

### Experience layer (REST API + Studio)

`src/worldspec/api/app.py` is a thin FastAPI router over `service.py` (business
logic stays out of routes). It serves the §12 endpoints and hosts the
dependency-free Studio (`api/static/`) at `/studio`. Launch with
`worldspec serve`.

### Compiler pipeline

```
WorldSpec YAML
  -> parser          (src/worldspec/compiler/parser)   line-tracked, eval-free
  -> AST             (src/worldspec/compiler/ast)       typed Pydantic models
  -> syntax checks   (in the parser)                    WS-SYN-* diagnostics
  -> semantic checks (src/worldspec/compiler/validator) WS-SEM-* diagnostics
  -> canonical IR    (src/worldspec/compiler/ir)        neutral JSON
  -> artifacts       (src/worldspec/compiler/generators) JSON Schema, manifest, .wspkg
```

`src/worldspec/compiler/pipeline.py` orchestrates the stages and is the single
entry point used by the CLI and tests. Semantic validation runs only when
parsing produced no structural errors, so cross-reference messages are never
spurious.

### Boundaries (see ADRs)

- The compiler depends on nothing below it (ADR-003).
- The runtime will depend on the **IR**, not raw YAML (ADR-002).
- Graph/relational stores sit behind repository interfaces (ADR-004).
- No `eval`; expressions are safe ASTs (ADR-005).
