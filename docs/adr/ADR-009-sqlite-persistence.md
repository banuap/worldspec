# ADR-009 — SQLite as the default durable store (behind the repository interface)

**Status:** Accepted

**Context.** The runtime needed durability for two things: registered packages
(so `worldspec deploy` survives restarts) and the **transition-event ledger**
(§15 / ADR-007) that must exist before any ML. The instructions recommend
PostgreSQL/Neo4j but also state local development must not require Kubernetes or
heavy infrastructure.

**Decision.** Define a `Store` interface (`runtime/store.py`) and ship two
implementations: an `InMemoryStore` (default, for tests and ephemeral use) and a
stdlib **`SqliteStore`** (durable, zero-infra). The store persists registered
packages and `TransitionEvent` records. A PostgreSQL/Neo4j store (ADR-004) can be
added later by implementing the same interface — no engine code changes.

**Consequences.** `worldspec deploy` / `worldspec serve --store …` give real
durability with no server to run. SQLite is opened with
`check_same_thread=False` plus a process lock because FastAPI dispatches handlers
across a threadpool. Concurrency is modest (single-process); a networked store is
the upgrade path when that ceases to hold.
