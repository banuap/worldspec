# ADR-001 — Use YAML for WorldSpec v0.1

**Status:** Accepted

**Context.** v0.1 needs an authoring format that humans and agents can write and
that has mature, safe parsers. A custom grammar/lexer would slow the first
vertical slice and is explicitly discouraged ("Do not add custom language syntax
until YAML semantics are stable", instructions §3).

**Decision.** Author WorldSpec models as YAML. Each top-level mapping key is
`"<construct> <Name>"`. Use PyYAML's `compose` API so we keep the node tree and
can attach source line numbers to diagnostics.

**Consequences.** Fast to implement and read; line-tracked errors. We accept
YAML quirks (e.g. silently-collapsed duplicate keys), mitigated by node-level
duplicate detection (`WS-SYN-0003`). A bespoke surface syntax can come later
without changing the IR (see ADR-002).
