# ADR-008 — Require evidence for every simulation

**Status:** Accepted (compiler support now; enforced by the runtime)

**Context.** Decisions must be explainable: a simulation must say which model
version, rules, and invariants produced its verdict (instructions §11.8, §14 —
"every risk score must be explainable").

**Decision.** Every construct compiles into the IR with stable identity
(`name`, `kind`, `severity`, etc.) so the runtime can cite exactly which
invariant/action/transition drove a result. The runtime's simulation API must
return an evidence object (model version, rules evaluated, invariants
passed/failed, assumptions, confidence, timestamp, recommended next step).

**Consequences.** v0.1 guarantees the *traceable inputs* (named, versioned IR).
The runtime milestone adds the evidence record itself. Opaque scoring is
disallowed.
