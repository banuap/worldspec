# Open questions & deferred work

Per operating rule 12, unresolved assumptions and intentionally-deferred work
are recorded here rather than guessed at in code.

## Done

- **Milestone 1** — language, compiler, IR, generators, CLI.
- **Milestone 2** — runtime: registry, entity/relationship/state services,
  invariant/action/transition engines, evidence, `worldspec simulate`.
- **Experience layer** — FastAPI REST API (§12) + dependency-free Studio with the
  five views (§16), served by `worldspec serve`.
- **Milestone 3** — end-to-end demo via `worldspec demo`.
- **Persistence + transition-event ledger** — durable SQLite store behind a
  repository interface (ADR-009); `worldspec deploy` is real; every simulation
  records a `TransitionEvent`; `POST /events/{id}/outcome` captures the observed
  result and computes `prediction_error` (the ML data gate, ADR-007).
- **Model builder (source adapter)** — `worldspec build` / `POST /models/build`
  / the Studio "Create Model" tab survey a repo and generate a validated model.
  Heuristic path (offline) emits a generic ontology + instances; LLM path
  (gated on `anthropic` + `ANTHROPIC_API_KEY`) emits a repo-tailored ontology
  and self-repairs once against compiler errors.

## Deferred to later milestones (by design)

- **Networked store (PostgreSQL/Neo4j)** — SQLite is the local default; a
  networked store implements the same `Store` interface (ADR-004/009) for
  multi-process use.
- **Studio polish & graph interactivity** — the Studio favours working semantics
  over polish; a richer graph (Cytoscape/React Flow) and live state editing are
  future work.
- **ML Phases 2-4** — the event ledger now exists, so Phase 2 (statistical
  risk/duration models) can begin once enough events are collected; the learned
  JEPA transition model (Phase 4) stays deferred until then (ADR-007).
- **ML / JEPA** — blocked until the runtime records the transition-event schema
  (`state_before, action, predicted_state_after, observed_state_after, outcome,
  prediction_error`). See ADR-007 and instructions §15.
- **Generators not yet built:** Neo4j constraints, SHACL shapes, GraphQL types,
  OpenAPI schemas. v0.1 emits only JSON Schema + manifest + IR because nothing
  consumes the others yet (operating rule 4). Add each when its consumer lands.
- **Persistence** (Neo4j/PostgreSQL/pgvector), **Docker Compose**, **OPA** — not
  required by the compiler; arrive with the runtime.

## Assumptions made in v0.1

- **Construct naming:** UpperCamelCase for all constructs except
  `relationship`, which is lowerCamelCase (matches the instructions' examples in
  §8.2 and §13). Recorded in the language spec §1.
- **Invariant expression path checking is a *warning* (`WS-SEM-0050`), not an
  error.** Paths can refer to derived/aggregate quantities (e.g.
  `activeWriters`) that are not always declared as a property or state
  dimension. Hard-failing would over-constrain modeling. The demo model declares
  all referenced paths so it is warning-free.
- **Action `from`/`to` context maps in transitions are free-form** scalars in
  v0.1; they are not yet validated against entity properties.
- **Line numbers** are tracked at construct and list-item granularity, not for
  every nested scalar. Sufficient for actionable diagnostics.
- **A `.wspkg` is a ZIP archive** containing `manifest.json`, `ontology.json`,
  `schemas/`, `docs/`. `policies/` and `queries/` directories from the suggested
  layout are omitted until policy/query generation exists.

## To revisit

- Should duplicate *property* names within an entity be a hard error? (YAML
  already collapses identical keys; we flag duplicate top-level keys via
  `WS-SYN-0003`.)
- Should `sum`/`min`/`max` aggregates require a numeric target type? Needs the
  runtime's value model to enforce meaningfully.
