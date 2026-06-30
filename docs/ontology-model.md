# Application-modernization ontology

This is the meta-model the demo (`models/application-modernization/`) instantiates.
The full target vocabulary is in instructions §13; the table below marks what is
modeled in v0.1.

## Entities

| Entity              | v0.1 |
|---------------------|:----:|
| Application         |  ✓   |
| Program             |  ✓   |
| BatchJob            |  ✓   |
| Dataset             |  ✓   |
| ReportingSystem     |  ✓   |
| Scheduler           |  ✓   |
| Control             |  ✓   |
| BusinessCapability  |  ✓   |
| Database, Table, API, File, Release, Incident, Owner, Environment, Execution | later |

## Relationships (v0.1)

`dependsOn`, `reads`, `writes`, `invokes`, `produces`, `consumes`,
`scheduledBy`, `governedBy`, `supports`, `replacedBy`.

## States (v0.1)

`DatasetState`, `ApplicationState`, `BatchState`, `CutoverState`.

## Invariants (v0.1)

`SingleWriter`, `SettlementBalance`, `BatchCompletionSLA`, `RollbackAvailable`.

## Actions (v0.1)

`ShadowRun`, `CompareOutputs`, `TransferReadAuthority`, `TransferWriteAuthority`,
`Rollback`.

## Transitions (v0.1)

`COBOLToJava` (the only one fully modeled in the first release, per §13).

## Modeling conventions

- An entity's **`properties`** are static identity/descriptive facts; its
  **`state` dimensions** are the things that change and that invariants/actions
  reason over.
- Invariant expression paths and action precondition/effect paths should resolve
  to a declared property or state dimension of the relevant entity; the
  validator warns (`WS-SEM-0050`/`0033`) when they don't.
