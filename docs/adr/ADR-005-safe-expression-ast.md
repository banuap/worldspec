# ADR-005 — Parse invariant/action expressions into a safe AST

**Status:** Accepted

**Context.** Invariants carry boolean expressions and actions carry
precondition/effect expressions. Evaluating these with `eval`/`exec` would be a
critical security hole, especially since models may be authored or suggested by
LLMs (treated as untrusted input, instructions §17).

**Decision.** Never use `eval`. Invariant expressions are authored as structured
mappings and parsed into typed AST nodes (`Comparison`, `Logical`, `PathRef`,
`Aggregate`, `Literal`). Action preconditions/effects use a tiny single-line
mini-language parsed with explicit tokenizing into `Predicate`/`Assignment`
nodes. Operators, functions, and comparators are drawn from closed allow-lists.

**Consequences.** All expressions are inert data structures the runtime can
evaluate deterministically. Malformed expressions become `WS-SYN-008x` /
`WS-SYN-005x` diagnostics rather than executing arbitrary code.
