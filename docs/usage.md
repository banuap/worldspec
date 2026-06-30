# Using WorldSpec against a codebase

This is a step-by-step guide for taking a real application estate — in **any
language or product**: a mainframe batch suite, a Java or .NET service fleet, a
Python data pipeline, a database platform, a mixed legacy + modern portfolio —
and turning it into a validated, compiled WorldSpec model. The examples below
use a COBOL→Java modernization for concreteness, but every step is
technology-neutral.

## Shortcut: generate a model from a repository

You can have WorldSpec draft a model for you instead of hand-authoring it:

```bash
worldspec build https://github.com/owner/repo --name my-model
```

or use the **Create Model** tab in the Studio (`worldspec serve`). It surveys the
repo, detects the stack, and generates a model — heuristic by default, or a
repo-tailored model when an LLM provider is configured (see below). The compiler
validates the result before it is saved, and it appears in the Studio
automatically. Treat the output as a **starting point** you refine with the
steps below.

### Configuring an LLM provider (optional)

The builder works fully offline (heuristic). For a richer, repo-tailored model,
configure one of these providers via environment variables or a gitignored
`.env` (the explicit `WORLDSPEC_LLM_PROVIDER` always wins; otherwise the
provider is inferred from whichever credential is present):

| Provider    | How to enable                                                                 |
|-------------|-------------------------------------------------------------------------------|
| **Gemini**  | `GEMINI_API_KEY=…` (or `GOOGLE_API_KEY`). No SDK needed.                       |
| **Anthropic** | `pip install anthropic` + `ANTHROPIC_API_KEY=…`.                            |
| **Copilot bridge / OpenAI-compatible** | `WORLDSPEC_LLM_PROVIDER=copilot` + `WORLDSPEC_LLM_BASE_URL=…` (see below). |

#### Using a VS Code Copilot bridge

If you already have GitHub Copilot in VS Code, you can route the builder through
it instead of a separate API key. Run a **Copilot bridge** — any tool that
exposes Copilot's models on a local OpenAI-compatible endpoint
(`/v1/chat/completions`) — then point WorldSpec at it:

```bash
# .env  (or export in your shell)
WORLDSPEC_LLM_PROVIDER=copilot
WORLDSPEC_LLM_BASE_URL=http://localhost:4141/v1   # your bridge's URL (this is the default)
WORLDSPEC_LLM_MODEL=gpt-4o                         # any model the bridge serves
WORLDSPEC_LLM_API_KEY=…                            # only if your bridge requires a token
```

```bash
worldspec build https://github.com/owner/repo --name my-model
worldspec serve            # the banner prints "LLM provider -> copilot (gpt-4o)"
```

This path uses the stdlib HTTP client (no extra dependency) and works with any
OpenAI-compatible gateway, not just Copilot. WorldSpec sends the bridge a
sampled survey of the repository; the compiler then validates whatever YAML
comes back, so a bad response fails loudly rather than producing an invalid
model. `WORLDSPEC_LLM_PROVIDER=openai` is accepted as an alias.

## Read this first: what WorldSpec does (and doesn't) do today

WorldSpec is a **declarative modeling language**, not a static-analysis scanner.
You describe your estate — its entities, how they relate, the states that
matter, the rules that must hold — and the compiler **validates that description
and compiles it to a governed package** (`.wspkg`).

> **Automated source ingestion is not built yet.** The instructions describe
> source adapters (code, config, scheduler metadata, data catalogs, events —
> with technology-specific variants per stack) that would read a codebase and
> emit a draft model. Those are a later milestone (see
> `docs/open-questions.md`). Today you author the model — by hand, or with an
> LLM/agent that reads the code and emits WorldSpec YAML, which you then run
> through this compiler.

So "running WorldSpec against a codebase" is a **two-part loop**:

```
  (1) derive a WorldSpec model from the codebase   [manual or agent-assisted]
  (2) validate -> compile -> package the model      [this compiler]
```

This guide covers both, with the compiler as the source of truth that keeps the
model honest.

---

## Step 0 — Install

```bash
cd worldspec
python -m pip install -e .          # add ".[dev]" if you want to run the tests
worldspec version                   # -> worldspec 0.1.0
```

## Step 1 — Create a model directory

```bash
worldspec init estates/payments     # writes estates/payments/model.yaml
```

A model is just a directory of `.yaml`/`.yml` files. Split it however you like —
all files in the directory are merged into one namespace, so a common layout is:

```
estates/payments/
  entities.yaml
  relationships.yaml
  states.yaml
  invariants.yaml
  actions.yaml
  transitions.yaml
```

(The bundled `models/application-modernization/` is a complete worked example you
can copy from.)

## Step 2 — Inventory the estate as `entity` constructs

Walk the codebase and list the *things that exist*. Map source artifacts to
entities:

| In the codebase…                                          | WorldSpec entity        |
|-----------------------------------------------------------|-------------------------|
| A deployable app / service / orchestration layer          | `Application`           |
| A unit of code (COBOL program, Java/.NET class, module)   | `Program`               |
| A scheduled unit of work (JCL step, cron job, Airflow DAG)| `BatchJob`              |
| A data store (VSAM file, table, topic, object, dataset)   | `Dataset`               |
| A downstream report/consumer system                       | `ReportingSystem`       |
| A reconciliation/governance check                         | `Control`               |
| The scheduler/orchestrator itself                         | `Scheduler`             |

For each, record the **static** facts as `properties` (an identity key plus
descriptive fields):

```yaml
entity Application:
  identity: [applicationId]
  properties:
    applicationId: { type: string, required: true }
    name: { type: string, required: true }
    orchestrationPlatform: { type: enum, values: [COBOL, Java] }
    criticality: { type: enum, values: [low, medium, high, systemic] }
```

> **Heuristic:** if a field *changes over the lifecycle of the system*, it
> belongs in a `state` (Step 4), not in `properties`.

## Step 3 — Capture dependencies as `relationship` constructs

From call graphs, JCL DD statements, schedules, and data lineage, record the
edges. Relationship names are **lowerCamelCase**:

```yaml
relationship writes:      # which jobs write which datasets — the dual-write hot spot
  from: BatchJob
  to: Dataset
  cardinality: many

relationship scheduledBy:
  from: BatchJob
  to: Scheduler
  cardinality: one
```

Useful edges to extract: `reads`, `writes`, `produces`, `consumes`, `invokes`,
`dependsOn`, `scheduledBy`, `governedBy`, `replacedBy`.

## Step 4 — Model the things that change as `state` constructs

For each entity whose status matters during a change, declare a `state` with the
`dimensions` you'll reason over:

```yaml
state DatasetState:
  entity: Dataset
  dimensions:
    lockMode: { type: enum, values: [none, shared, exclusive] }
    writeAuthority: { type: ref, target: Application }
    activeWriters: { type: int }
    unreconciledItems: { type: int }
```

## Step 5 — Encode the rules that must never break as `invariant` constructs

This is the heart of the value. Turn "the things that would cause an incident"
into invariants. Expressions are structured (no free-text, no `eval`):

```yaml
invariant SingleWriter:          # no dual-write during a cutover
  appliesTo: Dataset
  expression:
    operator: "<="
    left: { function: count, path: activeWriters }
    right: 1
  severity: critical
  onViolation: { action: block_transition }
```

`severity` ∈ `info|warning|high|critical`; `onViolation.action` ∈
`block_transition|warn|record`.

## Step 6 — Define `action`s and the `transition` you're assessing

Actions describe *permitted changes* with preconditions, effects, and rollback.
Preconditions/effects are a tiny safe one-line language (`path <op> value` /
`path = value`):

```yaml
action TransferWriteAuthority:
  inputs:
    dataset: { type: ref, target: Dataset }
    source:  { type: ref, target: Application }
    target:  { type: ref, target: Application }
  preconditions:
    - target.validationStatus == "passed"
    - dataset.lockMode == "none"
  effects:
    - dataset.writeAuthority = target
  rollback:
    - dataset.writeAuthority = source

transition COBOLToJava:
  action: TransferWriteAuthority
  from: { orchestrationPlatform: COBOL }
  to:   { orchestrationPlatform: Java }
  preserves: [ SingleWriter, SettlementBalance, RollbackAvailable ]
```

## Step 7 — Validate, and iterate on the diagnostics

```bash
worldspec validate estates/payments/
```

The compiler tells you exactly what's wrong, where, with a stable code and a
suggestion. This is the loop that keeps your model faithful to the codebase —
e.g. a typo'd invariant name:

```
[x] ERROR WS-SEM-0042
transition COBOLToJava references unknown invariant 'RollbackReady'.
Line: 6
Suggestion: Did you mean 'RollbackAvailable'?
```

Fix and re-run until you see:

```
[ok] estates/payments: valid (32 constructs, 0 warning(s)).
```

Warnings (e.g. `WS-SEM-0050` for a path you haven't declared, `WS-SEM-0032` for
an action with no rollback) don't fail the build but flag modeling gaps worth
closing.

## Step 8 — Compile to a package

```bash
worldspec compile estates/payments/ --output build/payments.wspkg
```

You get a `.wspkg` (a zip) containing:

```
manifest.json                 # name, versions, construct counts
ontology.json                 # the canonical IR — the stable contract
schemas/<Entity>.schema.json  # JSON Schema per entity
docs/README.txt
```

Downstream consumers depend on the **IR**, never the raw YAML.

## Step 9 — Inspect / hand off

```bash
worldspec inspect build/payments.wspkg
```

```
[ok] payments  (package 0.1.0)
  language 0.1.0  compiler 0.1.0
  constructs:
    action        5
    entity        8
    ...
```

---

## Putting it in CI

`validate` exits non-zero on errors and supports machine-readable output, so a
pull-request gate is one line:

```bash
worldspec validate estates/payments/ --json
```

Example GitHub Actions step:

```yaml
- name: Validate WorldSpec model
  run: |
    python -m pip install -e .
    worldspec validate estates/payments/ --json
```

Any change to the model that breaks a reference, an enum, or an invariant fails
the build before it merges.

---

## Driving the compiler from Python (build your own tooling)

If you're building an agent that reads a repo and emits WorldSpec, or a service
that compiles models on demand:

```python
from worldspec.compiler import validate_model, compile_model

result = compile_model("estates/payments")        # also: compile_text(yaml_str)
if not result.ok:
    for d in result.errors:                        # stable codes for programmatic handling
        print(d.code, d.message, d.file, d.line, d.suggestion)
else:
    ir = result.ir                                 # canonical JSON IR (dict)
    model = result.model                           # typed AST: model.entities, model.invariants, ...
```

`CompileResult` exposes `.ok`, `.errors`, `.warnings`, `.model` (typed AST), and
`.ir` (JSON). Use `validate_text` / `compile_text` for in-memory strings.

This is exactly the integration point a future **source adapter** would use (for
any stack): read source/config/schedule metadata → emit WorldSpec YAML →
`compile_text` → `.wspkg`.

---

## Diagnostic codes you'll see most

| Code         | Meaning                                                       |
|--------------|---------------------------------------------------------------|
| `WS-SYN-0010`| Malformed top-level key (not `"<construct> <Name>"`)          |
| `WS-SYN-0011`| Unknown construct keyword                                     |
| `WS-SYN-0012`| Bad name case (UpperCamelCase; relationships lowerCamelCase)  |
| `WS-SYN-0030`| Missing required field                                        |
| `WS-SYN-0040/41/42`| Bad type / enum without values / ref without target    |
| `WS-SYN-0050/51`| Malformed invariant expression / operator               |
| `WS-SYN-0080/81`| Unparseable precondition / effect                       |
| `WS-SEM-0001/02`| Reference to an unknown entity                          |
| `WS-SEM-0010`| Identity names a property that isn't declared                 |
| `WS-SEM-0031`| Action path root isn't a declared input                       |
| `WS-SEM-0040`| Transition references an unknown action                       |
| `WS-SEM-0042`| Transition preserves an unknown invariant                     |

Full grammar: `docs/language-spec-v0.1.md`. A complete example to learn from:
`models/application-modernization/`.

---

## What this does *not* do yet

- The **model builder** (`worldspec build`) drafts a model from a repo, but the
  offline heuristic produces a generic starter (real understanding requires the
  LLM path); either way you refine the result by hand.
- It does **not** run a live simulation: `worldspec deploy` and
  `worldspec simulate` are honest stubs until the runtime (Milestone 2) lands.
  At that point you'll load the `.wspkg`, set real state, and have the invariant
  engine actually detect violations and recommend a safer trajectory.

See `docs/demo-scenario.md` for the end-to-end story and `docs/open-questions.md`
for the roadmap.
