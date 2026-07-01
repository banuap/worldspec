# WorldSpec

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21077393.svg)](https://doi.org/10.5281/zenodo.21077393)
[![Spec: v0.1](https://img.shields.io/badge/spec-v0.1-blue)](https://w3id.org/worldspec/spec/0.1/)
[![License: AGPL v3](https://img.shields.io/badge/code-AGPL--3.0-blue)](LICENSE)
[![Spec license: CC BY 4.0](https://img.shields.io/badge/spec-CC--BY--4.0-lightgrey)](LICENSE-spec)

> **Model the enterprise. Predict the transition. Preserve what matters.**

WorldSpec is a declarative language and compiler for modeling enterprise
systems as **entities, relationships, states, invariants, actions, and
transitions**. It gives humans and AI agents a shared, governed representation
of an application estate so that proposed changes can be checked against
critical invariants *before* execution.

WorldSpec is **technology-agnostic** — the same six constructs model any
software product in any language (mainframe batch, microservices, data
pipelines, database platforms, cloud re-platformings). The first bundled
worked example is **application modernization and cutover assurance** — a
COBOL/JCL/VSAM → Java transition — chosen as one concrete, high-stakes
illustration, not as a limit.

New here? Start with **[`docs/what-is-worldspec.md`](docs/what-is-worldspec.md)**
— a plain-language overview with a complete example model.

## What's in this build (Milestones 1–4)

**Milestone 1 — language & compiler** (instructions §23):

- the WorldSpec v0.1 YAML language (`docs/language-spec-v0.1.md`),
- a safe parser with line-tracked diagnostics (no `eval`),
- syntax + semantic validation with stable error codes (`WS-SYN-*`, `WS-SEM-*`),
- a canonical JSON **IR** that the runtime depends on,
- artifact generators (JSON Schema, manifest) and a `.wspkg` package,
- a CI-friendly CLI: `worldspec validate | compile | inspect | init`.

**Milestone 2 — runtime** (instructions §11): a runtime that loads a compiled
`.wspkg`, holds typed entity/relationship/state instances, and runs the
**invariant → action → transition** engines to simulate a proposed change and
return explainable **evidence**:

- model registry, entity/relationship/state services (in-memory, behind
  interfaces — no database required locally, ADR-004),
- a safe invariant evaluator (walks the expression AST, never `eval`s),
- an action engine (preconditions, effects, reversible plans),
- a transition engine that builds a candidate future state, checks the preserved
  invariants, scores risk (explainable weighted formula), and derives a safer
  trajectory **from the model itself**,
- `worldspec simulate`, plus demo models (`application-modernization`,
  `swing-legacy-assessment`, and `short-interest-rebate` — a broker-dealer
  securities-lending estate, see [`docs/example-short-interest-rebate.md`](docs/example-short-interest-rebate.md)),
- a test suite (**77 tests**, 91% total; compiler core ≥ 90%, runtime core ≥ 90%).

**Experience layer — REST API + Studio** (§12, §16): a FastAPI service exposes
the runtime (`/models`, `/transitions/simulate`, `/evidence/{id}`,
`/world/inspect`, …) and hosts a dependency-free **Studio** with five views
(model browser, dependency graph, state inspector, transition simulator,
evidence panel):

```bash
pip install -e ".[api]"
worldspec serve            # -> http://127.0.0.1:8000/studio/  (+ /docs)
```

**Milestone 3 — demo** (§20): one command proves the whole story end to end:

```bash
worldspec demo             # estate -> current-state checks -> blocked cutover -> safer path
```

**Model builder (source adapter)** — point WorldSpec at a repository and it
surveys the code and generates a model; the compiler validates it before it is
saved. Heuristic by default (works offline); LLM-tailored when a provider is
configured — Gemini, Anthropic, or a **VS Code Copilot bridge** /
OpenAI-compatible endpoint (`WORLDSPEC_LLM_PROVIDER=copilot`,
see [`docs/usage.md`](docs/usage.md#configuring-an-llm-provider-optional)):

```bash
worldspec build https://github.com/owner/repo --name my-model
# or in the Studio: the "Create Model" tab
```

**Persistence + transition-event ledger** (the ML prerequisite, §15 / ADR-007):
a durable SQLite store (behind a repository interface, ADR-009) persists
registered packages and records a `TransitionEvent` for every simulation
(`state_before`, `predicted_state_after`); observed outcomes are captured and
turned into `prediction_error`:

```bash
worldspec deploy models/application-modernization     # durable register
worldspec events                                       # the recorded ledger
# POST /events/{id}/outcome  records the observed result + prediction error
```

Only the **ML models** themselves remain unbuilt — now correctly *unblocked*:
the event ledger exists, so Phase 2 (statistical risk/duration models) can begin
once enough events are collected; the learned JEPA model stays deferred (ADR-007).

## Quick start

```bash
python -m pip install -e .          # or: pip install -e ".[dev]"

worldspec validate models/application-modernization/
worldspec compile  models/application-modernization/ \
  --output build/application-modernization.wspkg
worldspec inspect  build/application-modernization.wspkg

# Simulate a proposed change against an observed world (Milestone 2):
worldspec simulate COBOLToJava \
  --model models/application-modernization \
  --context examples/investone-like-demo/context.json
```

The simulation detects the dual-write `SingleWriter` violation, blocks the
cutover, scores the risk, and recommends a safer path derived from the model:

```text
[x] COBOLToJava -> BLOCKED  (risk: critical)
    [x] [critical] SingleWriter is VIOLATED for instance 'SETTLEMENT.VSAM': count(activeWriters)=2 <= 1
  Recommended trajectory:
    ShadowRun -> CompareOutputs -> TransferWriteAuthority
```

For a full step-by-step of modeling a real estate and running the compiler
against it (including CI and the Python API), see **`docs/usage.md`**.

Validation is CI-friendly:

```text
$ worldspec validate models/application-modernization/
[ok] models/application-modernization: valid (32 constructs, 0 warning(s)).
```

…and fails clearly, with a stable code, file, line, and a suggestion:

```text
[x] ERROR WS-SEM-0042
transition JavaCutover references unknown invariant 'BatchSLA'.
File: .../transitions.yaml
Line: 4
Suggestion: Did you mean 'BatchCompletionSLA'?
```

## Repository layout

```
src/worldspec/
  compiler/
    ast/         typed AST (Pydantic v2)
    parser/      YAML -> AST + syntax validation (line-tracked, eval-free)
    validator/   semantic validation (cross-references)
    ir/          canonical JSON IR
    generators/  JSON Schema, manifest, .wspkg package
    pipeline.py  parse -> validate -> IR
  cli/           Typer CLI
models/application-modernization/   the demo ontology (the COBOLToJava estate)
docs/            language spec, architecture, ADRs, open questions
tests/           unit + semantic + negative + CLI tests
```

## Development

```bash
python -m pytest -q                              # run tests
python -m pytest --cov=worldspec --cov-report=term-missing
```

See `AGENTS.md` for the operating rules this codebase is built under and
`docs/open-questions.md` for recorded assumptions and deferred work.

## Specification

WorldSpec is published as an open, implementable specification:

- **Spec (v0.1):** <https://w3id.org/worldspec/spec/0.1/> — syntax, type
  system, expression/action grammars (EBNF), canonical IR, and conformance.
- **Namespace:** <https://w3id.org/worldspec/ns/0.1/>
- **Model JSON Schema:** [`docs/schemas/worldspec-model-0.1.schema.json`](docs/schemas/worldspec-model-0.1.schema.json)
- **Conformance suite:** [`conformance/`](conformance/) · **Governance/versioning:** [`GOVERNANCE.md`](GOVERNANCE.md)
- **Publishing the spec (Pages, w3id, Zenodo, IANA):** [`PUBLISHING.md`](PUBLISHING.md)

WorldSpec is **free to implement**: the specification carries a royalty-free
implementation grant, so independent tools can target it without permission.

**For LLMs/agents:** WorldSpec is machine-consumable — any model can author
conforming WorldSpec from context. See
[`/llms.txt`](https://w3id.org/worldspec/llms.txt) (discovery index),
[`/llms-full.txt`](https://w3id.org/worldspec/llms-full.txt) (whole
language in one file), and the
[authoring prompt](docs/authoring-with-an-llm.md).

## License

The **reference implementation** (this repository's code) is licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later).
Note: the AGPL requires that if you run a modified version of this software to
provide a network service, you must make the corresponding source code
available to users of that service.

The **specification** (the `docs/spec/`, `docs/ns/`, `docs/schemas/`, and
`conformance/` artifacts) is licensed separately under
[Creative Commons Attribution 4.0 International](LICENSE-spec) (CC BY 4.0), with
a royalty-free grant to build conforming implementations. The AGPL copyleft
applies only to this repository's code, never to the language or to independent
implementations.
