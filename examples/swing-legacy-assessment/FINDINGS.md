# WorldSpec assessment — Trading-Simulation-Platform (legacy Java Swing)

**Target:** `Mykyta-G/Trading-Simulation-Platform` — a Java Swing desktop stock-trading simulator (4 source files, ~2,250 LOC).
**Mode:** assess legacy as-is. No cutover. The goal is to surface latent defects.
**Model:** `models/swing-legacy-assessment/` → compiled to `build/swing-legacy-assessment.wspkg`.

WorldSpec gives the estate a **governed, declarative catalog of risks** (8 invariants
over 6 entity types). Below, each invariant is mapped to the concrete code that
would violate it, with a severity and the remediation action the model defines.

| # | Invariant | Severity | Status | Evidence |
|---|-----------|----------|:------:|----------|
| 1 | `NoPlaintextCredentials` | critical | **VIOLATED** | `ProfileManager.java:511, 543` |
| 2 | `NoBlockingIoOnEDT` | critical | **VIOLATED** | `Main.java:776-777`; `ProfileManager.java:88-92, 599, 685` |
| 3 | `NoBusinessLogicInView` | high | **VIOLATED** | `Main.java:501-650` |
| 4 | `SingleWriterPerState` | high | **VIOLATED** | `Main.java:45, 249, 279, 297`; `ProfileManager.java:620, 635` |
| 5 | `BoundedUnitComplexity` | high | **VIOLATED** | `Main.java:40-924` (`main()` ≈ 884 lines) |
| 6 | `NoStructuralUiTraversal` | high | **VIOLATED** | `Main.java:950-1019, 1035-1076` |
| 7 | `ViewDoesNotPersist` | high | **VIOLATED** | `ProfileManager.java:506-529, 685-741` |
| 8 | `RobustPersistenceFormat` | warning | **VIOLATED** | `ProfileManager.java:628, 642, 708-728` |

---

## 1. `NoPlaintextCredentials` — credentials stored in plaintext *(critical)*

Passwords are written to disk verbatim and compared with `String.equals`:

```java
// ProfileManager.java:511
writer.println("password:" + password);
// ProfileManager.java:543
return password.equals(storedPassword);
```

`CredentialStore.storageScheme == plaintext`. The invariant requires
`storageScheme != "plaintext"`.
**Remediation action:** `HashCredentials` → `salted_hashed`, `encryptionAtRest = true`.

## 2. `NoBlockingIoOnEDT` — synchronous file I/O on the Event Dispatch Thread *(critical)*

`saveUserData()`/`loadUserData()` do blocking `FileReader`/`FileWriter` work and run
on the EDT — from the 500 ms price `Timer`, the auto-save `Timer`, button clicks,
and `windowClosing`:

```java
// Main.java:776-777  (inside a 500ms Swing Timer callback — runs on the EDT)
if (profileManager.isLoggedIn()) { profileManager.saveUserData(); }
// ProfileManager.java:88-92  (auto-save Swing Timer → saveUserData on the EDT)
autoSaveTimer = new Timer(5000, e -> { if (isLoggedIn) { saveUserData(); } });
```

`ThreadState{executesOn: edt, performsBlockingIo: true}`. The invariant forbids the
combination. **Remediation action:** `MoveIoOffEdt` (→ `worker`, via `SwingWorker`).

## 3. `NoBusinessLogicInView` — trading logic embedded in button listeners *(high)*

Affordability checks and balance/holdings mutation live directly inside the Buy/Sell
`ActionListener`s in `main()`:

```java
// Main.java:507-515
if (balance[0] >= currentPrice) {
    balance[0] -= currentPrice;
    ...
    stocksOwned.put(stockName, owned);
}
```

`UiComponent.containsBusinessLogic == true`. **Remediation action:**
`ExtractServiceLayer` into a `Service` (e.g. `TradingService`).

## 4. `SingleWriterPerState` — shared mutable state with multiple writers *(high)*

`balance` (a `double[]` used as a mutable box), `stocksOwned`, and `currentPrices`
are created in `Main` and passed **by reference** into `ProfileManager` (and
`ProfileNotes`), then written from both sides:

```java
// Main.java:45 / 249 / 279
double[] balance = {1000.0};
Map<String,Double> currentPrices = new HashMap<>();
Map<String,Integer> stocksOwned = new HashMap<>();
// Main.java:297  shared by reference
profileManager = new ProfileManager(frame, stocksOwned, balance, currentPrices);
// ProfileManager.java:620 / 635  second writer overwrites the same state
balance[0] = savedBalance;
stocksOwned.put(stockName, quantity);
```

`StateOwnership.writerCount > 1`. **Remediation action:** `ConsolidateStateOwnership`
(single owner, e.g. a `Portfolio` service).

## 5. `BoundedUnitComplexity` — god method *(high)*

`Main.main()` spans `Main.java:40-924` (≈ 884 lines): UI construction, styling, the
price-simulation loop, trade handling, and persistence triggers all in one static
method. `ComponentQualityState.lineCount` ≫ 200.

## 6. `NoStructuralUiTraversal` — UI mutated by walking the container tree *(high)*

Price/owned labels are found by recursively scanning the component tree and
matching on rendered text:

```java
// Main.java:1006     // and 976, 1043
if (text != null && text.startsWith("$")) { label.setText("$" + ...); }
// Main.java:1035    recursive findAndUpdateComponents(...)
```

This couples behavior to layout and label strings. `traversesContainerTree == true`.
**Remediation action:** `RemoveUiTraversal` (bind to a model, not the view tree).

## 7. `ViewDoesNotPersist` — UI class performs persistence directly *(high)*

`ProfileManager` is a UI class (builds dialogs, panels, icons) that *also* owns file
persistence and authentication (`registerUser`, `authenticate`, `saveUserData`,
`loadUserData`, `ProfileManager.java:506-741`). No repository/DAO boundary.
**Remediation action:** `ExtractServiceLayer` + a persistence boundary.

## 8. `RobustPersistenceFormat` — ad-hoc delimited persistence *(warning)*

Profiles are stored as colon-delimited lines and parsed with `split(":")`, which is
fragile (any value containing `:` breaks it) and unversioned:

```java
// ProfileManager.java:642
String[] parts = line.split(":");   // transaction:STOCK:TYPE:PRICE:QTY:TIMESTAMP
```

`PersistenceState.schemaVersioned == false`. Move to a versioned JSON/DB format.

---

## How this was produced

```bash
worldspec validate models/swing-legacy-assessment/
worldspec compile  models/swing-legacy-assessment/ -o build/swing-legacy-assessment.wspkg
worldspec inspect  build/swing-legacy-assessment.wspkg
```

The model validates with **0 errors / 0 warnings** and compiles to a `.wspkg`
containing the canonical IR + per-entity JSON Schemas.

## What WorldSpec proves here (and what is next)

- **Today:** the risks are captured as a *governed, versioned, machine-readable*
  contract — not a one-off review. The same `.wspkg` can gate any future change to
  this app.
- **Next (Milestone 2 runtime):** load the `.wspkg`, attach the observed values
  above as entity state, and have the invariant engine **flag each violation
  automatically** and score the remediation trajectory (`HashCredentials` →
  `MoveIoOffEdt` → `ExtractServiceLayer` → `ConsolidateStateOwnership`). The
  evidence mapping in this document is exactly what that engine would emit.
