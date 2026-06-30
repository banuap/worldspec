# ADR-004 — Use Neo4j behind a repository abstraction

**Status:** Accepted (applies to the runtime milestone; not yet implemented)

**Context.** The estate is naturally a graph (dependencies, reads/writes, impact
traversal). The runtime will need graph queries, but the compiler must not
depend on any store.

**Decision.** When the runtime is built, Neo4j will be the graph store, accessed
only through a repository interface so the store is swappable and testable with
an in-memory fake. No graph-store code appears in the compiler.

**Consequences.** Recorded now so future work conforms; nothing in this build
imports a database driver. Tracked in `docs/open-questions.md`.
