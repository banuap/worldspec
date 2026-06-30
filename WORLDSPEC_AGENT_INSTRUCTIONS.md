# WorldSpec — Agent Development Instructions

## 1. Mission

Build **WorldSpec**, a declarative language, compiler, runtime, and developer experience for modeling enterprise systems as:

- entities
- relationships
- states
- invariants
- actions
- transitions
- observations
- evidence
- trajectories

WorldSpec should allow humans and AI agents to describe an enterprise application estate, evaluate proposed changes, detect invariant violations, simulate state transitions, and recommend safer modernization paths.

The first product use case is:

> **Application modernization and cutover assurance for legacy systems, beginning with a COBOL/JCL/VSAM-to-Java transition scenario.**

Do not begin with a generalized enterprise ontology platform. Build a narrow, working vertical slice.

---

## 2. Product Principle

WorldSpec is not another agent framework.

It is the **enterprise semantic and state-transition foundation** that agents, LLMs, causal models, and future JEPA-style world models use to understand:

1. what exists,
2. how it is related,
3. what state it is in,
4. what actions are permitted,
5. what must remain invariant,
6. what consequences may follow from a proposed change.

The product must support the following lifecycle:

```text
Observe current system
→ represent system state
→ define proposed action
→ evaluate invariants
→ simulate transition
→ explain consequences
→ recommend safer trajectory
→ capture observed outcome
→ learn from prediction error
```

---

## 3. Initial Product Scope

The first release must support six core WorldSpec constructs:

```text
entity
relationship
state
invariant
action
transition
```

The second release may add:

```text
observation
policy
objective
prediction
trajectory
evidence
```

Do not add custom language syntax until YAML semantics are stable.

---

## 4. First Demonstration Scenario

Build a synthetic financial-services modernization estate with:

- one COBOL orchestration layer,
- one Java replacement candidate,
- 10–15 batch jobs,
- 4–6 VSAM datasets,
- two downstream reporting systems,
- one settlement capability,
- one reconciliation process,
- one scheduler,
- one shared write-authority risk.

The demonstration must answer:

> What happens if orchestration moves from COBOL to Java while shared datasets and downstream jobs remain unchanged?

The system should detect:

- dual-write risk,
- shared-dataset contention,
- impacted downstream jobs,
- SLA risk,
- reconciliation-control gaps,
- rollback-readiness gaps.

It should recommend a phased path such as:

```text
Shadow run
→ compare outputs
→ validate invariants
→ transfer read authority
→ transfer write authority
→ retain rollback window
→ decommission legacy orchestration
```

---

## 5. Required Architecture

Use the following logical architecture.

```text
┌────────────────────────────────────────────────────┐
│ Experience Layer                                   │
│ CLI | Studio | REST API | Graph View | Simulation  │
└─────────────────────────┬──────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────┐
│ WorldSpec Runtime                                  │
│ Registry | State | Invariants | Actions |          │
│ Transitions | Evidence | Simulation                │
└─────────────────────────┬──────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────┐
│ Compiler                                           │
│ Parser | AST | Semantic Validation | IR |          │
│ Artifact Generators                                │
└─────────────────────────┬──────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────┐
│ Semantic Persistence                              │
│ Neo4j | PostgreSQL | pgvector | Object Storage     │
└─────────────────────────┬──────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────┐
│ Source Adapters                                    │
│ COBOL | JCL | VSAM metadata | Scheduler | Events   │
└────────────────────────────────────────────────────┘
```

---

## 6. Recommended Technology Stack

Use the following unless there is a compelling technical reason to change it.

| Concern | Technology |
|---|---|
| Language implementation | Python 3.12+ |
| YAML parsing | ruamel.yaml or PyYAML |
| Validation/types | Pydantic v2 |
| CLI | Typer |
| API runtime | FastAPI |
| Graph store | Neo4j |
| Relational metadata/state | PostgreSQL |
| Vector storage | pgvector |
| Event streaming | Redpanda or Kafka |
| Policy enforcement | Open Policy Agent |
| UI | Next.js + React + TypeScript |
| Graph visualization | Cytoscape.js or React Flow |
| Testing | pytest |
| Packaging | Poetry or uv |
| Containers | Docker Compose initially |
| Telemetry | OpenTelemetry |
| ML later | PyTorch + PyTorch Geometric |

Do not require Kubernetes for local development.

---

## 7. Repository Structure

Create a monorepo with this structure:

```text
worldspec/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── docs/
│   ├── product-vision.md
│   ├── language-spec-v0.1.md
│   ├── architecture.md
│   ├── ontology-model.md
│   └── demo-scenario.md
├── compiler/
│   ├── parser/
│   ├── ast/
│   ├── validator/
│   ├── ir/
│   ├── generators/
│   └── tests/
├── runtime/
│   ├── registry/
│   ├── entities/
│   ├── state/
│   ├── invariants/
│   ├── actions/
│   ├── transitions/
│   ├── simulation/
│   ├── evidence/
│   └── tests/
├── cli/
├── api/
├── studio/
├── connectors/
│   ├── cobol/
│   ├── jcl/
│   ├── vsam/
│   └── scheduler/
├── models/
│   └── application-modernization/
├── examples/
│   └── investone-like-demo/
└── tests/
    ├── integration/
    └── acceptance/
```

---

## 8. WorldSpec v0.1 Language

Use YAML as the authoring format.

### 8.1 Entity

```yaml
entity Application:
  description: A deployable enterprise software system

  identity:
    - applicationId

  properties:
    applicationId:
      type: string
      required: true

    name:
      type: string
      required: true

    criticality:
      type: enum
      values: [low, medium, high, systemic]

    lifecycle:
      type: enum
      values: [active, modernizing, retiring]
```

### 8.2 Relationship

```yaml
relationship dependsOn:
  from: Application
  to: Application
  cardinality: many
  temporal: true
```

### 8.3 State

```yaml
state DatasetState:
  entity: Dataset

  dimensions:
    availability:
      type: enum
      values: [available, unavailable]

    lockMode:
      type: enum
      values: [none, shared, exclusive]

    writeAuthority:
      type: ref
      target: Application
```

### 8.4 Invariant

```yaml
invariant SingleWriter:
  appliesTo: Dataset

  expression:
    operator: "<="
    left:
      function: count
      path: activeWriters
    right: 1

  severity: critical

  onViolation:
    action: block_transition
```

### 8.5 Action

```yaml
action TransferWriteAuthority:
  inputs:
    dataset:
      type: ref
      target: Dataset

    source:
      type: ref
      target: Application

    target:
      type: ref
      target: Application

  preconditions:
    - target.validationStatus == "passed"
    - dataset.lockMode == "none"

  effects:
    - dataset.writeAuthority = target

  rollback:
    - dataset.writeAuthority = source
```

### 8.6 Transition

```yaml
transition JavaCutover:
  action: TransferWriteAuthority

  from:
    orchestrationPlatform: COBOL

  to:
    orchestrationPlatform: Java

  preserves:
    - SingleWriter
    - SettlementBalance
    - BatchCompletionSLA
    - RollbackAvailable
```

---

## 9. Compiler Responsibilities

The compiler must implement this pipeline:

```text
WorldSpec YAML
→ parser
→ AST
→ syntax validation
→ semantic validation
→ canonical intermediate representation
→ generated artifacts
→ deployable WorldSpec package
```

### 9.1 Syntax Validation

Validate:

- required fields,
- valid data types,
- valid enum definitions,
- valid construct names,
- no duplicate names,
- correct expression structure.

### 9.2 Semantic Validation

Validate:

- referenced entities exist,
- relationships use valid source and target types,
- referenced properties exist,
- action effects target valid state dimensions,
- transitions reference valid actions,
- preserved invariants exist,
- rollback definitions are valid,
- no circular type references that make compilation impossible.

### 9.3 Canonical Intermediate Representation

Compile every construct into a neutral JSON representation.

Example:

```json
{
  "kind": "invariant",
  "name": "SingleWriter",
  "targetType": "Dataset",
  "expression": {
    "operator": "<=",
    "left": {
      "function": "count",
      "path": "activeWriters"
    },
    "right": 1
  },
  "severity": "critical"
}
```

The runtime must depend on the IR, not on raw YAML.

### 9.4 Generated Artifacts

Generate:

- JSON Schema,
- Neo4j constraints and indexes,
- SHACL shapes,
- GraphQL types,
- OpenAPI schemas,
- documentation,
- a model manifest,
- a package artifact.

Package format:

```text
application-modernization.wspkg
```

Suggested contents:

```text
manifest.json
ontology.json
schemas/
policies/
queries/
docs/
```

---

## 10. CLI Requirements

Implement:

```bash
worldspec init
worldspec validate <file-or-directory>
worldspec compile <file-or-directory>
worldspec inspect <package>
worldspec deploy <package>
worldspec simulate <transition> --context <json-file>
worldspec test <model-directory>
```

Example:

```bash
worldspec validate models/application-modernization/
worldspec compile models/application-modernization/ \
  --output build/application-modernization.wspkg
```

CLI output must be clear, actionable, and suitable for CI/CD.

Example error:

```text
ERROR WS-SEM-0042
Transition 'JavaCutover' references unknown invariant 'BatchSLA'.

File: transitions/java-cutover.yaml
Line: 14
Suggestion: Did you mean 'BatchCompletionSLA'?
```

---

## 11. Runtime Services

Implement the following runtime components.

### 11.1 Model Registry

Responsibilities:

- register compiled packages,
- store package versions,
- activate/deactivate versions,
- return model metadata,
- prevent incompatible overwrites.

### 11.2 Entity Service

Responsibilities:

- create/update/query typed entities,
- validate entity identity,
- validate property types,
- enforce required fields.

### 11.3 Relationship Service

Responsibilities:

- create and query typed relationships,
- validate relationship cardinality,
- maintain temporal validity,
- support impact traversal.

### 11.4 State Service

Responsibilities:

- store current state,
- preserve state history,
- support point-in-time queries,
- support predicted and observed states,
- distinguish valid time and transaction time where practical.

### 11.5 Invariant Engine

Responsibilities:

- evaluate invariants against current or simulated state,
- classify severity,
- explain violations,
- block transitions when required,
- produce machine-readable and human-readable evidence.

### 11.6 Action Engine

Responsibilities:

- validate action inputs,
- check preconditions,
- calculate proposed effects,
- apply policy checks,
- generate a reversible execution plan.

### 11.7 Transition Engine

Responsibilities:

- create candidate future states,
- validate preserved invariants,
- return affected entities and relationships,
- expose rollback path,
- return confidence and evidence.

### 11.8 Evidence Service

Every decision must include:

- model version,
- source data references,
- rules evaluated,
- invariants passed/failed,
- assumptions,
- confidence,
- timestamp,
- actor,
- proposed action,
- recommended next step.

---

## 12. Required Runtime APIs

Implement these initial endpoints:

```http
GET  /health
GET  /models
POST /models/register
GET  /models/{model_id}

POST /entities
GET  /entities/{type}
GET  /entities/{type}/{id}

POST /relationships
GET  /relationships/impact/{entity_id}

GET  /state/{entity_id}
GET  /state/{entity_id}/history

POST /invariants/validate
POST /actions/evaluate
POST /transitions/simulate
GET  /evidence/{decision_id}
```

Example simulation request:

```json
{
  "model": "application-modernization",
  "transition": "JavaCutover",
  "context": {
    "application": "GS-Orchestrator",
    "dataset": "SETTLEMENT.VSAM"
  }
}
```

Example response:

```json
{
  "allowed": false,
  "riskLevel": "critical",
  "violations": [
    {
      "invariant": "SingleWriter",
      "reason": "COBOL and Java both retain active write authority"
    }
  ],
  "impactedEntities": [
    "JOB.SETTLE.020",
    "REPORT.DAILY.POSITIONS",
    "SETTLEMENT.VSAM"
  ],
  "recommendedTrajectory": [
    "ShadowRun",
    "CompareOutputs",
    "TransferReadAuthority",
    "TransferWriteAuthority"
  ]
}
```

---

## 13. Application Modernization Ontology

The first model must include at least these entities:

```text
Application
Program
BatchJob
Dataset
Database
Table
API
File
BusinessCapability
Control
Release
Incident
Owner
Environment
Scheduler
Execution
```

Relationships:

```text
dependsOn
reads
writes
invokes
produces
consumes
implements
supports
ownedBy
deployedTo
governedBy
scheduledBy
failedDuring
replacedBy
```

States:

```text
ApplicationState
BatchState
DatasetState
MigrationState
ValidationState
CutoverState
ExecutionState
```

Invariants:

```text
SingleWriter
SettlementBalance
BatchCompletionSLA
NoOrphanDependency
SchemaCompatibility
ControlCoverage
RollbackAvailable
OutputEquivalence
RequiredUpstreamCompleted
NoUnapprovedProductionWrite
```

Actions:

```text
Deploy
ShadowRun
CompareOutputs
TransferReadAuthority
TransferWriteAuthority
Rollback
Retire
Replace
ReorderJob
ChangeSchema
DisableWriter
EnableWriter
```

Transitions:

```text
COBOLToJava
MainframeToCloud
VSAMToDatabase
OracleToPostgreSQL
MonolithToServices
BatchToEventDriven
```

Only `COBOLToJava` needs full end-to-end implementation in the first release.

---

## 14. Simulation Logic for v0.1

Do not implement JEPA in v0.1.

Use:

- graph traversal,
- deterministic state changes,
- invariant evaluation,
- weighted risk scoring,
- rule-based trajectory generation.

Suggested risk formula:

```text
risk_score =
  invariant_violation_weight
+ impacted_critical_entities_weight
+ rollback_gap_weight
+ control_gap_weight
+ uncertainty_weight
```

Normalize risk to:

```text
low
medium
high
critical
```

Every risk score must be explainable.

---

## 15. ML and JEPA Roadmap

Do not train a learned world model until the runtime records:

```text
state_before
action
predicted_state_after
observed_state_after
outcome
prediction_error
```

Introduce ML in this order:

### Phase 1

Rule-based and graph-based simulation.

### Phase 2

Statistical models for:

- batch-duration risk,
- failure probability,
- rollback likelihood,
- output-divergence probability.

### Phase 3

Temporal graph and graph-neural-network models.

### Phase 4

JEPA-inspired action-conditioned latent transition model.

The eventual learned model should estimate:

```text
z(t+1) = Predictor(z(t), action, context)
```

But all predictions must remain anchored to:

- explicit ontology,
- current system state,
- known constraints,
- evidence,
- uncertainty.

---

## 16. User Interface Requirements

Build a minimal WorldSpec Studio with five views.

### 16.1 Model Browser

Show:

- entities,
- relationships,
- states,
- invariants,
- actions,
- transitions.

### 16.2 Dependency Graph

Allow users to:

- select an entity,
- view upstream/downstream dependencies,
- filter by relationship type,
- highlight critical entities.

### 16.3 State Inspector

Show:

- current state,
- historical state,
- predicted state,
- source evidence.

### 16.4 Transition Simulator

Allow users to:

- choose a transition,
- select context entities,
- enter parameters,
- run a simulation,
- compare candidate trajectories.

### 16.5 Evidence Panel

Show:

- violated invariants,
- passed checks,
- affected systems,
- supporting data,
- confidence,
- recommended actions.

Do not prioritize visual polish over working semantics.

---

## 17. Engineering Standards

### Code Quality

- Use type hints everywhere.
- Keep business logic out of API routes.
- Keep compiler and runtime modules independent.
- Prefer pure functions for parsing and validation.
- Use dependency injection for persistence adapters.
- Document public APIs.
- Reject silent failure.
- Provide stable error codes.

### Testing

Each feature must include:

- unit tests,
- semantic-validation tests,
- runtime behavior tests,
- integration tests,
- at least one negative test.

Target:

```text
compiler coverage: >= 90%
runtime core coverage: >= 85%
```

### Security

- Never execute arbitrary expressions using `eval`.
- Parse invariant expressions into a safe AST.
- Enforce model-level and entity-level authorization hooks.
- Record every action evaluation.
- Treat generated LLM output as untrusted input.
- Do not allow an agent to execute a transition without policy approval.

### Versioning

Version independently:

- language version,
- model version,
- compiler version,
- runtime version,
- package format version.

Use semantic versioning.

---

## 18. Agent Operating Rules

The development agent must follow these rules.

1. Read this file before making changes.
2. Inspect the existing repository before creating new files.
3. Implement the smallest end-to-end working increment.
4. Do not create speculative abstractions without an immediate use case.
5. Preserve backwards compatibility unless a migration is provided.
6. Add tests before marking a feature complete.
7. Update documentation when semantics change.
8. Never bypass semantic validation for convenience.
9. Never hard-code the demo ontology into the runtime.
10. Keep graph-store-specific code behind repository interfaces.
11. Explain important design decisions in ADRs.
12. Record unresolved assumptions in `docs/open-questions.md`.
13. Do not implement JEPA until the transition-event schema is complete.
14. Do not add autonomous execution in v0.1.
15. Prefer explainability over opaque scoring.
16. Ensure every simulation returns evidence.
17. Ensure every state mutation is reversible or explicitly marked irreversible.
18. Use deterministic behavior in tests.
19. Never expose credentials in code or examples.
20. Finish each task with a concise implementation summary and test results.

---

## 19. Architectural Decision Records

Create ADRs for major decisions.

Initial ADRs:

```text
ADR-001 Use YAML for WorldSpec v0.1
ADR-002 Use canonical JSON IR
ADR-003 Separate compiler from runtime
ADR-004 Use Neo4j behind a repository abstraction
ADR-005 Use safe expression AST for invariants
ADR-006 Use bitemporal state where practical
ADR-007 Defer JEPA until transition data exists
ADR-008 Require evidence for every simulation
```

---

## 20. Delivery Plan

### Milestone 1 — Language and Compiler

Deliver:

- language specification,
- YAML parser,
- AST,
- semantic validator,
- canonical IR,
- CLI validation,
- package generation.

Acceptance:

```bash
worldspec validate models/application-modernization/
worldspec compile models/application-modernization/
```

Both commands succeed for valid input and fail clearly for invalid input.

### Milestone 2 — Runtime

Deliver:

- model registry,
- entity/relationship services,
- state service,
- invariant engine,
- action engine,
- transition simulator,
- evidence service.

Acceptance:

- runtime loads a `.wspkg`,
- creates demo entities,
- evaluates `SingleWriter`,
- simulates `JavaCutover`,
- returns evidence.

### Milestone 3 — Demo

Deliver:

- synthetic estate,
- dependency graph,
- current-state view,
- Java cutover simulation,
- invariant violation,
- recommended safer trajectory.

Acceptance:

The demo must visibly prove:

> WorldSpec can model a real enterprise system, detect when a proposed change violates critical invariants, and recommend a safer transition path.

### Milestone 4 — Studio

Deliver:

- model browser,
- graph view,
- state inspector,
- simulation view,
- evidence panel.

---

## 21. Definition of Done

A task is done only when:

- implementation is complete,
- tests pass,
- documentation is updated,
- API behavior is documented,
- errors are actionable,
- no secrets are committed,
- acceptance criteria are demonstrated,
- technical debt is recorded.

A milestone is done only when it works from a clean checkout using documented commands.

---

## 22. Initial Commands to Support

The repository should eventually support:

```bash
git clone <repo>
cd worldspec
cp .env.example .env
docker compose up -d
uv sync
worldspec validate models/application-modernization/
worldspec compile models/application-modernization/ \
  --output build/application-modernization.wspkg
worldspec deploy build/application-modernization.wspkg
worldspec simulate JavaCutover \
  --context examples/investone-like-demo/context.json
```

---

## 23. First Implementation Task

Begin with this task:

> Implement the WorldSpec v0.1 parser, AST, semantic validator, canonical IR, and CLI for `entity`, `relationship`, `state`, `invariant`, `action`, and `transition`.

Required deliverables:

1. `docs/language-spec-v0.1.md`
2. sample YAML model
3. typed AST classes
4. safe parser
5. syntax validator
6. semantic validator
7. JSON IR generator
8. `worldspec validate`
9. `worldspec compile`
10. comprehensive tests

Do not implement the web UI or machine learning before this is complete.

---

## 24. Product Definition

Use this as the canonical product description:

> **WorldSpec is a declarative language and runtime for modeling enterprise entities, relationships, states, invariants, actions, and transitions. It gives humans, AI agents, causal models, and world models a shared, governed representation of the enterprise and allows proposed actions to be simulated before execution.**

Use this as the initial product promise:

> **Model the enterprise. Predict the transition. Preserve what matters.**
