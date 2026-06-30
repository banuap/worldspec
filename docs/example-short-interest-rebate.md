# Example — Short Interest Rebate (securities lending), a broker-dealer estate

This is a second worked example, from **capital-markets / broker-dealer
modernization**. It models the **short-interest rebate** process — the heart of
a securities-lending (stock-loan) book — and the rules that must keep holding
while the **rebate-calculation engine is migrated from a legacy platform to a
target platform**.

The full, validated model is bundled at
[`models/short-interest-rebate/`](../models/short-interest-rebate/model.yaml)
(`worldspec validate models/short-interest-rebate/` → *18 constructs, 0
warnings*).

> Like the COBOL→Java demo, this is one illustration of a technology-neutral
> language. See [`what-is-worldspec.md`](what-is-worldspec.md) for the basics.

---

## The business process, in plain terms

When a hedge fund wants to **short** a stock, it must first **borrow** the
shares to deliver to the buyer. A broker-dealer's **stock-loan desk** lends
those shares and, in return, takes **cash collateral** from the borrower —
typically **102%** of the shares' market value (US convention).

The desk holds that cash and pays the borrower interest on it, called the
**rebate**, at the **rebate rate**:

```
rebate rate  =  benchmark rate (e.g. SOFR/Fed Funds)  −  borrow fee
```

- For easy-to-borrow ("general collateral") names, the borrow fee is tiny and
  the rebate is close to the benchmark.
- For **hard-to-borrow** ("special") names, the fee is large and the rebate can
  even go **negative** — the borrower pays to hold the short.

Every day the loan is **marked to market**: if the stock rises, the borrower
must post **more** collateral (a **margin call**); if it falls, collateral is
returned. The lender can **recall** the shares, the borrower can **return**
them, and the loan finally **settles**. If a recall isn't met, the desk does a
**buy-in**.

**Why this is a modernization risk:** the rebate, collateral, and
mark-to-market math often live in decades-old systems. Re-platforming that
engine while loans are live can silently under-collateralize a book or
mis-price rebates — exactly the kind of failure WorldSpec invariants catch
*before* a cutover.

---

## How it maps to WorldSpec

| Business concept                         | WorldSpec construct                                   |
|------------------------------------------|-------------------------------------------------------|
| The borrowable stock                     | `entity Security` (+ `SecurityState`)                 |
| Borrower / lender (fund, custodian, desk)| `entity Counterparty`                                 |
| One borrow contract                      | `entity StockLoan` (+ `LoanState`)                    |
| "This loan is on IBM, borrowed by Fund A"| `relationship onSecurity` / `borrowedBy` / `lentBy`   |
| Collateral must be ≥ 102%                | `invariant FullyCollateralized`                       |
| Rebate never exceeds the benchmark       | `invariant RebateWithinBenchmark`                     |
| You can't lend more shares than you hold | `invariant NoOversupply`                              |
| Open / recall / return / settle the loan | `action`s `OpenLoan`, `RecallLoan`, … (reversible)    |
| A margin call tops collateral back to 102%| `action PostMarginCall`                              |
| Migrating the rebate engine              | `transition RebateEngineCutover`                      |

### The model

```yaml
# entities — the things that exist
entity Security:        # the borrowable instrument (CUSIP/ticker)
  identity: [securityId]
  properties:
    securityId: { type: string, required: true }
    ticker:     { type: string, required: true }
    cusip:      { type: string }

entity Counterparty:    # a borrower or lender
  identity: [counterpartyId]
  properties:
    counterpartyId: { type: string, required: true }
    name:           { type: string, required: true }
    role:           { type: enum, values: [borrower, lender, both] }

entity StockLoan:       # one securities-lending contract
  identity: [loanId]
  properties:
    loanId:    { type: string, required: true }
    tradeDate: { type: datetime }

# relationships — the loan graph
relationship onSecurity: { from: StockLoan, to: Security,     cardinality: one }
relationship borrowedBy: { from: StockLoan, to: Counterparty, cardinality: one }
relationship lentBy:     { from: StockLoan, to: Counterparty, cardinality: one }

# state — what changes day to day
state SecurityState:
  entity: Security
  dimensions:
    marketPrice:       { type: float }
    availableQuantity: { type: int }   # shares still lendable from inventory
    hardToBorrow:      { type: bool }  # "special" name?
    borrowFeeBps:      { type: int }   # lending fee in basis points

state LoanState:
  entity: StockLoan
  dimensions:
    status:                    { type: enum, values: [pending, open, recalled, returned, settled, boughtIn] }
    loanQuantity:              { type: int }
    collateralPosted:          { type: float }
    marketValue:               { type: float }
    collateralizationRatioBps: { type: int }   # 10200 == 102.00%
    benchmarkRateBps:          { type: int }   # e.g. SOFR
    rebateRateBps:             { type: int }   # benchmark − fee (can be negative)
    accruedRebate:             { type: float }
    marginCallOpen:            { type: bool }

# invariants — the rules that must always hold
invariant FullyCollateralized:        # collateral must stay ≥ 102%
  appliesTo: StockLoan
  expression: { operator: ">=", left: { path: collateralizationRatioBps }, right: 10200 }
  severity: critical
  onViolation: { action: block_transition }

invariant RebateWithinBenchmark:      # never pay a rebate above the benchmark
  appliesTo: StockLoan
  expression: { operator: "<=", left: { path: rebateRateBps }, right: { path: benchmarkRateBps } }
  severity: high
  onViolation: { action: warn }

invariant NoOversupply:               # can't lend shares you don't have
  appliesTo: Security
  expression: { operator: ">=", left: { path: availableQuantity }, right: 0 }
  severity: critical
  onViolation: { action: block_transition }

# actions — permitted, reversible changes
action PostMarginCall:                # resolve a margin call back to 102%
  inputs: { loan: { type: ref, target: StockLoan } }
  preconditions: [ "loan.marginCallOpen == true" ]
  effects:       [ "loan.collateralizationRatioBps = 10200", "loan.marginCallOpen = false" ]
  rollback:      [ "loan.marginCallOpen = true" ]

action RecallLoan:
  inputs: { loan: { type: ref, target: StockLoan } }
  preconditions: [ "loan.status == \"open\"" ]
  effects:       [ "loan.status = \"recalled\"" ]
  rollback:      [ "loan.status = \"open\"" ]

# transition — migrate the rebate engine while preserving the critical rules
transition RebateEngineCutover:
  action: PostMarginCall
  from: { rebateEngine: legacy }
  to:   { rebateEngine: target }
  preserves: [ FullyCollateralized, RebateWithinBenchmark, PositiveLoanQuantity ]
```

*(Abridged for readability — the bundled file also declares `OpenLoan`,
`ReturnShares`, `SettleLoan`, and the `PositiveLoanQuantity` invariant.)*

---

## What the cutover assurance buys you

The `RebateEngineCutover` transition declares it must **preserve**
`FullyCollateralized`, `RebateWithinBenchmark`, and `PositiveLoanQuantity`.
Once the runtime milestone lands, you load real loans, point the desk at the
**target** engine, and the invariant engine answers:

- Does any loan drop below 102% collateral under the new engine? →
  `FullyCollateralized` **blocks** the cutover.
- Does the new rebate math ever pay above the benchmark? →
  `RebateWithinBenchmark` flags it.

Today (compiler milestone) the value is already real: the model *compiles and
cross-validates*, and the `.wspkg` names exactly which rules the cutover is
contractually required to keep.

---

## Glossary — business and tech terms

| Term | Business meaning | Tech / WorldSpec representation |
|------|------------------|----------------------------------|
| **Short interest** | Shares sold short and not yet covered; the demand side that drives borrowing. | The population of `StockLoan` entities with `status = open`. |
| **Securities lending / stock loan** | Lending shares to a short-seller against collateral. | The whole model; one loan = one `StockLoan`. |
| **Rebate** | Interest the lender pays the borrower on cash collateral. | `LoanState.rebateRateBps` (in basis points). |
| **Rebate rate** | `benchmark − borrow fee`; can be negative for specials. | `rebateRateBps`; rule `rebateRateBps <= benchmarkRateBps`. |
| **Benchmark rate** | Reference short rate (SOFR, Fed Funds). | `LoanState.benchmarkRateBps`. |
| **Borrow fee / lending fee** | What the borrower pays to borrow a name. | `SecurityState.borrowFeeBps`. |
| **Hard-to-borrow ("special")** | Scarce name with a high fee / negative rebate. | `SecurityState.hardToBorrow: bool`. |
| **Collateral** | Cash (or securities) the borrower posts, usually 102%. | `LoanState.collateralPosted`. |
| **Collateralization ratio** | collateral ÷ market value; must stay ≥ 102%. | `collateralizationRatioBps` (10200 = 102%); `invariant FullyCollateralized`. |
| **Mark-to-market (MTM)** | Daily re-valuation of the loan vs. current price. | Updating `marketValue` + `collateralizationRatioBps`. |
| **Margin call** | Demand for more collateral after an MTM shortfall. | `LoanState.marginCallOpen`; resolved by `action PostMarginCall`. |
| **Recall** | Lender demands the shares back. | `action RecallLoan` → `status = recalled`. |
| **Return** | Borrower gives the shares back. | `action ReturnShares` → `status = returned`. |
| **Buy-in** | Forced market purchase when a recall isn't met. | `status = boughtIn` (modeled; action deferred). |
| **Settlement** | Final close-out of the loan and collateral. | `action SettleLoan` → `status = settled`. |
| **Basis point (bps)** | 1/100th of a percent; rates are quoted in bps. | Integer `*Bps` dimensions (avoids float rounding). |
| **Counterparty** | The fund/custodian/desk on the other side. | `entity Counterparty`, `role ∈ {borrower, lender, both}`. |
| **Rebate engine** | The system that computes rebates/collateral daily. | The thing being migrated: `from/to` of `transition RebateEngineCutover`. |

---

## See also

- [`what-is-worldspec.md`](what-is-worldspec.md) — the language in five minutes.
- [`usage.md`](usage.md) — author your own model from a real codebase.
- [`demo-scenario.md`](demo-scenario.md) — the COBOL/JCL/VSAM → Java example.

> **Want the Order/Offer (order-lifecycle) example too?** It models the trade
> side — `Order`, `Offer`/quote, matching, and execution, with invariants like
> *no execution above the displayed offer* and *filled ≤ ordered*. Ask and it
> can be added as a third bundled model alongside this one.
