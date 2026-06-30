# ADR-007 — Defer JEPA until transition data exists

**Status:** Accepted

**Context.** A learned, action-conditioned world model (JEPA-style) is the
long-term vision, but it requires observed transition data to train against and
must remain anchored to the explicit ontology (instructions §15).

**Decision.** v0.1 uses no machine learning. Simulation (Milestone 2+) will be
rule-/graph-based and deterministic. ML is introduced only after the runtime
records the full transition-event schema: `state_before, action,
predicted_state_after, observed_state_after, outcome, prediction_error`.

**Consequences.** No ML dependencies in this build. The ontology + IR are the
substrate any future predictor will be conditioned on.

**Update (Persistence stage).** The transition-event schema now exists and is
recorded: every simulation persists `state_before`, `action`,
`predicted_state_after`, and—once an outcome is observed via
`POST /events/{id}/outcome`—`observed_state_after`, `outcome`, and
`prediction_error` (`runtime/events.py`, `runtime/store.py`). This is the data
gate the ADR set; **Phase 2 statistical models may begin once enough events are
collected.** JEPA (Phase 4) remains deferred.
