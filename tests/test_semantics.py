"""Semantic-validation tests (cross-reference checks)."""

from worldspec.compiler.pipeline import validate_text


def codes(result):
    return {d.code for d in result.diagnostics}


def diag(result, code):
    return next(d for d in result.diagnostics if d.code == code)


def test_unknown_ref_target():
    text = """
entity A:
  identity: [id]
  properties:
    id: { type: string }
    other: { type: ref, target: Ghost }
"""
    r = validate_text(text)
    assert "WS-SEM-0001" in codes(r) and not r.ok


def test_relationship_unknown_entity():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
relationship rel:
  from: A
  to: Ghost
  cardinality: one
"""
    assert "WS-SEM-0002" in codes(validate_text(text))


def test_identity_property_must_exist():
    text = """
entity A:
  identity: [missing]
  properties:
    id: { type: string }
"""
    assert "WS-SEM-0010" in codes(validate_text(text))


def test_state_unknown_entity():
    text = """
state S:
  entity: Ghost
  dimensions:
    d: { type: int }
"""
    assert "WS-SEM-0020" in codes(validate_text(text))


def test_invariant_unknown_entity():
    text = """
invariant Inv:
  appliesTo: Ghost
  expression: { operator: "==", left: { path: x }, right: 1 }
  severity: high
"""
    assert "WS-SEM-0021" in codes(validate_text(text))


def test_transition_unknown_invariant_matches_spec_example():
    """Reproduces the WS-SEM-0042 example from the agent instructions (§10)."""
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  effects: [ "a.id = \\"x\\"" ]
  rollback: [ "a.id = \\"y\\"" ]
invariant BatchCompletionSLA:
  appliesTo: A
  expression: { operator: "==", left: { path: id }, right: 1 }
  severity: high
transition JavaCutover:
  action: Act
  preserves: [ BatchSLA ]
"""
    r = validate_text(text)
    d = diag(r, "WS-SEM-0042")
    assert "JavaCutover" in d.message and "BatchSLA" in d.message
    assert d.suggestion and "BatchCompletionSLA" in d.suggestion
    assert not r.ok


def test_transition_unknown_action():
    text = """
transition T:
  action: Ghost
  preserves: []
"""
    assert "WS-SEM-0040" in codes(validate_text(text))


def test_action_path_root_must_be_input():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  effects:
    - notaninput.id = "x"
"""
    assert "WS-SEM-0031" in codes(validate_text(text))


def test_action_without_rollback_warns_irreversible():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  effects:
    - a.id = "x"
"""
    r = validate_text(text)
    assert "WS-SEM-0032" in codes(r)
    # A warning alone must not fail validation.
    assert r.ok
