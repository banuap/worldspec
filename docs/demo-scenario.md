# Demo scenario — COBOL → Java orchestration cutover

The `models/application-modernization/` model is a synthetic financial-services
estate (instructions §4). It exists to answer one question:

> What happens if orchestration moves from COBOL to Java while shared datasets
> and downstream jobs remain unchanged?

## The estate (modeled today)

- **Applications:** a COBOL orchestration layer and a Java replacement
  candidate (`entity Application`, `orchestrationPlatform ∈ {COBOL, Java}`).
- **Shared data:** VSAM-like `Dataset`s with a `DatasetState` carrying
  `lockMode`, `writeAuthority`, `readAuthority`, `activeWriters`,
  `unreconciledItems`.
- **Work:** `BatchJob`s that `read`/`write`/`produce` datasets and are
  `scheduledBy` a `Scheduler`; `ReportingSystem`s that `consume` outputs.
- **Controls:** reconciliation `Control`s that `governedBy` datasets.

## The risks the model encodes (as invariants)

| Invariant            | Guards against                                  |
|----------------------|-------------------------------------------------|
| `SingleWriter`       | dual-write risk (COBOL + Java both writing)     |
| `SettlementBalance`  | reconciliation-control gap (unreconciled items) |
| `BatchCompletionSLA` | SLA / batch-duration risk                       |
| `RollbackAvailable`  | rollback-readiness gap                          |

## The safer trajectory (encoded as actions)

```
ShadowRun -> CompareOutputs -> TransferReadAuthority -> TransferWriteAuthority
(with Rollback available throughout)
```

The `COBOLToJava` transition declares it must `preserve` `SingleWriter`,
`SettlementBalance`, `BatchCompletionSLA`, and `RollbackAvailable`.

## What's provable today vs. next

- **Today (compiler):** the estate, its invariants, the cutover action and
  transition all *compile* and cross-validate; the IR/`.wspkg` names exactly
  which invariants the transition must preserve.
- **Next (runtime, Milestone 2):** load the `.wspkg`, create demo entities, set
  a dual-write state, and have the invariant engine *detect* the `SingleWriter`
  violation and recommend the phased trajectory above. The expected simulation
  request/response is in `examples/investone-like-demo/`.
