"""Parser + syntax-validation tests, including negative cases."""

from worldspec.compiler.ast import Aggregate, Comparison, Logical, PathRef
from worldspec.compiler.pipeline import validate_text


def codes(result):
    return {d.code for d in result.diagnostics}


def test_parses_all_six_constructs():
    text = """
entity Dataset:
  identity: [datasetId]
  properties:
    datasetId: { type: string, required: true }

relationship governedBy:
  from: Dataset
  to: Dataset
  cardinality: many

state DatasetState:
  entity: Dataset
  dimensions:
    lockMode: { type: enum, values: [none, shared] }

invariant SingleWriter:
  appliesTo: Dataset
  expression:
    operator: "<="
    left: { function: count, path: lockMode }
    right: 1
  severity: critical

action DoThing:
  inputs:
    dataset: { type: ref, target: Dataset }
  effects:
    - dataset.lockMode = "none"
  rollback:
    - dataset.lockMode = "shared"

transition T:
  action: DoThing
  preserves: [SingleWriter]
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    m = r.model
    assert set(m.entities) == {"Dataset"}
    assert set(m.relationships) == {"governedBy"}
    assert set(m.states) == {"DatasetState"}
    assert set(m.invariants) == {"SingleWriter"}
    assert set(m.actions) == {"DoThing"}
    assert set(m.transitions) == {"T"}


def test_invariant_expression_structure():
    text = """
entity Dataset:
  identity: [datasetId]
  properties:
    datasetId: { type: string, required: true }

invariant Combo:
  appliesTo: Dataset
  expression:
    operator: and
    operands:
      - operator: "<="
        left: { function: count, path: datasetId }
        right: 1
      - operator: "=="
        left: { path: datasetId }
        right: "ok"
  severity: warning
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    expr = r.model.invariants["Combo"].expression
    assert isinstance(expr, Logical) and expr.operator == "and"
    first, second = expr.operands
    assert isinstance(first, Comparison)
    assert isinstance(first.left, Aggregate) and first.left.function == "count"
    assert isinstance(second.left, PathRef)


def test_action_predicate_and_assignment_parsed_safely():
    text = """
entity App:
  identity: [id]
  properties:
    id: { type: string, required: true }

action A:
  inputs:
    app: { type: ref, target: App }
  preconditions:
    - app.status == "passed"
  effects:
    - app.status = "done"
  rollback:
    - app.status = "passed"
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    act = r.model.actions["A"]
    pre = act.preconditions[0]
    assert pre.left.segments == ["app", "status"]
    assert pre.operator == "=="
    assert pre.right.value == "passed"
    eff = act.effects[0]
    assert eff.target.segments == ["app", "status"]
    assert eff.value.value == "done"


# --------------------------- negative cases ------------------------------- #


def test_malformed_top_level_key():
    r = validate_text("not a construct: {}")
    assert "WS-SYN-0010" in codes(r) and not r.ok


def test_unknown_construct_keyword_suggests():
    r = validate_text("entty Foo:\n  properties: {}\n")
    assert "WS-SYN-0011" in codes(r)
    d = next(d for d in r.diagnostics if d.code == "WS-SYN-0011")
    assert d.suggestion and "entity" in d.suggestion


def test_bad_construct_name_case():
    r = validate_text("entity lowercaseName:\n  identity: [x]\n  properties:\n    x: {type: string}\n")
    assert "WS-SYN-0012" in codes(r)


def test_relationship_must_be_lower_camel():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
relationship BadName:
  from: A
  to: A
  cardinality: one
"""
    assert "WS-SYN-0012" in codes(validate_text(text))


def test_duplicate_name():
    text = """
entity Dup:
  identity: [id]
  properties: { id: { type: string } }
entity Dup:
  identity: [id]
  properties: { id: { type: string } }
"""
    assert "WS-SYN-0003" in codes(validate_text(text))


def test_invalid_type():
    text = """
entity A:
  identity: [id]
  properties:
    id: { type: strng }
"""
    assert "WS-SYN-0040" in codes(validate_text(text))


def test_enum_requires_values():
    text = """
entity A:
  identity: [id]
  properties:
    id: { type: string }
    k: { type: enum }
"""
    assert "WS-SYN-0041" in codes(validate_text(text))


def test_bad_invariant_operator():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Bad:
  appliesTo: A
  expression:
    operator: "≈"
    left: { path: id }
    right: 1
  severity: high
"""
    assert "WS-SYN-0051" in codes(validate_text(text))


def test_bad_precondition_syntax():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs:
    a: { type: ref, target: A }
  preconditions:
    - this is not a predicate
  effects:
    - a.id = "x"
"""
    assert "WS-SYN-0080" in codes(validate_text(text))


def test_missing_required_field():
    # entity with no properties
    r = validate_text("entity A:\n  identity: [id]\n")
    assert "WS-SYN-0030" in codes(r)
