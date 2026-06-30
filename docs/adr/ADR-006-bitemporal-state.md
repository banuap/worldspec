# ADR-006 — Use bitemporal state where practical

**Status:** Accepted (applies to the runtime milestone; not yet implemented)

**Context.** The runtime must distinguish predicted vs observed state and answer
point-in-time queries (instructions §11.4).

**Decision.** Runtime state records will carry both valid time (when a fact was
true in the world) and transaction time (when it was recorded), where practical.
The language already separates an entity's static `properties` from its dynamic
`state` dimensions, which is the hook for temporal storage.

**Consequences.** No impact on the v0.1 compiler. Documented so the state schema
is designed bitemporally from the start.
