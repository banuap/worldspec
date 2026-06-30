# WorldSpec conformance suite

This suite is the machine-checkable authority for the conformance criteria in
the [WorldSpec Language Specification](https://banuap.github.io/worldspec/spec/0.1/)
(§Conformance). Any implementation — not just the reference one — can run it to
check itself.

## Layout

```
conformance/
  manifest.json          # the list of cases and their expected outcomes
  valid/<case>/model.yaml     # MUST compile with zero error diagnostics
  invalid/<case>/model.yaml   # MUST fail; manifest names the expected WS-* code
```

Each case is a **directory** (a WorldSpec model is a directory of `.yaml`
files), so multi-file cases are supported by adding more files to a case dir.

## Expected outcomes (v0.1.0)

| Case | Expect | Code |
|------|--------|------|
| `valid/minimal` | valid | — |
| `invalid/unknown-invariant` | error | `WS-SEM-0042` |
| `invalid/bad-name-case` | error | `WS-SYN-0012` |

## Running it against the reference implementation

```bash
# each valid case must succeed, each invalid case must fail with its code
worldspec validate conformance/valid/minimal/                 # -> [ok] ...
worldspec validate conformance/invalid/unknown-invariant/     # -> WS-SEM-0042, non-zero exit
worldspec validate conformance/invalid/bad-name-case/         # -> WS-SYN-0012, non-zero exit
```

`worldspec validate --json` emits machine-readable diagnostics (a `diagnostics`
array of objects carrying a stable `code`), which a harness can compare against
`manifest.json`.

## Running it against another implementation

A conforming validator MUST, for every case: report `ok` for `valid/` cases and
at least one `error`-severity diagnostic for `invalid/` cases. Emitting the
exact `code` named in the manifest is RECOMMENDED (the codes are part of the
specification's contract).

## Contributing cases

Every change that affects conformance MUST add cases here in the same change
set as the spec edit (see `../GOVERNANCE.md`). A good `invalid/` case isolates
exactly one rule and is named for it.
