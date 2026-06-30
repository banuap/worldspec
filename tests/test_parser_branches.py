"""Targeted coverage of parser error branches (syntax validation, §9.1)."""

from pathlib import Path

from worldspec.compiler.parser import parse_model
from worldspec.compiler.pipeline import validate_text


def codes(result):
    return {d.code for d in result.diagnostics}


def vcodes(text):
    r = validate_text(text)
    return {d.code for d in r.diagnostics}


def test_yaml_parse_error():
    assert "WS-SYN-0001" in vcodes("entity A:\n  : : :\n - broken")


def test_top_level_not_mapping():
    assert "WS-SYN-0002" in vcodes("- just\n- a\n- list\n")


def test_empty_document_is_ok():
    r = validate_text("")
    assert r.diagnostics == []


def test_body_not_mapping():
    assert "WS-SYN-0020" in vcodes("entity A: 123\n")


def test_type_decl_not_mapping():
    text = "entity A:\n  identity: [id]\n  properties:\n    id: notamapping\n"
    assert "WS-SYN-0040" in vcodes(text)


def test_enum_duplicate_values():
    text = "entity A:\n  identity: [id]\n  properties:\n    id: {type: string}\n    k: {type: enum, values: [a, a]}\n"
    assert "WS-SYN-0041" in vcodes(text)


def test_ref_missing_target():
    text = "entity A:\n  identity: [id]\n  properties:\n    id: {type: string}\n    r: {type: ref}\n"
    assert "WS-SYN-0042" in vcodes(text)


def test_member_name_not_lower_camel():
    text = "entity A:\n  identity: [id]\n  properties:\n    id: {type: string}\n    BadName: {type: string}\n"
    assert "WS-SYN-0090" in vcodes(text)


def test_relationship_bad_cardinality():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
relationship rel:
  from: A
  to: A
  cardinality: lots
"""
    assert "WS-SYN-0070" in vcodes(text)


def test_invalid_severity():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression: { operator: "==", left: { path: id }, right: 1 }
  severity: catastrophic
"""
    assert "WS-SYN-0060" in vcodes(text)


def test_invalid_on_violation():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression: { operator: "==", left: { path: id }, right: 1 }
  severity: high
  onViolation: { action: explode }
"""
    assert "WS-SYN-0061" in vcodes(text)


def test_not_takes_one_operand():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression:
    operator: not
    operands:
      - { operator: "==", left: { path: id }, right: 1 }
      - { operator: "==", left: { path: id }, right: 2 }
  severity: high
"""
    assert "WS-SYN-0051" in vcodes(text)


def test_unknown_aggregate_function():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression: { operator: "==", left: { function: median, path: id }, right: 1 }
  severity: high
"""
    assert "WS-SYN-0051" in vcodes(text)


def test_expression_without_operator():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression: { left: { path: id }, right: 1 }
  severity: high
"""
    assert "WS-SYN-0050" in vcodes(text)


def test_logical_requires_operands_list():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
invariant Inv:
  appliesTo: A
  expression: { operator: and }
  severity: high
"""
    assert "WS-SYN-0050" in vcodes(text)


def test_bad_effect_assignment_syntax():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  effects:
    - a.id "x"
"""
    assert "WS-SYN-0081" in vcodes(text)


def test_action_missing_effects():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
"""
    assert "WS-SYN-0030" in vcodes(text)


def test_preconditions_must_be_list():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  preconditions: "a.id == 1"
  effects: [ "a.id = \\"x\\"" ]
"""
    assert "WS-SYN-0031" in vcodes(text)


def test_numeric_and_bool_operands_in_actions():
    text = """
entity A:
  identity: [id]
  properties: { id: { type: string } }
action Act:
  inputs: { a: { type: ref, target: A } }
  preconditions:
    - a.count >= 3
    - a.flag == true
  effects:
    - a.count = 5
    - a.ratio = 1.5
    - a.flag = false
  rollback:
    - a.count = 0
"""
    r = validate_text(text)
    act = r.model.actions["Act"]
    assert act.effects[0].value.value == 5
    assert act.effects[1].value.value == 1.5
    assert act.effects[2].value.value is False


def test_action_operands_accept_single_quotes():
    # LLMs commonly emit single-quoted string literals; both quote styles are valid.
    text = """
entity Campaign:
  identity: [id]
  properties: { id: { type: string }, status: { type: enum, values: [Draft, Active] } }
action ActivateCampaign:
  inputs: { campaign: { type: ref, target: Campaign } }
  preconditions:
    - campaign.status == 'Draft'
  effects:
    - campaign.status = 'Active'
  rollback:
    - campaign.status = 'Draft'
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    act = r.model.actions["ActivateCampaign"]
    assert act.preconditions[0].right.value == "Draft"
    assert act.effects[0].value.value == "Active"


def test_action_unquoted_literals_treated_as_values():
    # LLMs often emit unquoted enum/string literals on the RHS; a bare word that
    # isn't a declared input is a string literal, not a path reference.
    text = """
entity Campaign:
  identity: [id]
  properties:
    id: { type: string }
    status: { type: enum, values: [Draft, Active] }
    createdBy: { type: string }
action CreateCampaign:
  inputs: { campaign: { type: ref, target: Campaign } }
  preconditions:
    - campaign.status == Draft
  effects:
    - campaign.status = Active
    - campaign.createdBy = admin
  rollback:
    - campaign.status = Draft
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    act = r.model.actions["CreateCampaign"]
    assert act.preconditions[0].right.kind == "value" and act.preconditions[0].right.value == "Draft"
    assert act.effects[0].value.value == "Active"
    assert act.effects[1].value.value == "admin"


def test_action_input_ref_still_a_path():
    # A bare token that IS an input remains a path reference (e.g. `= target`).
    text = """
entity Dataset:
  identity: [id]
  properties: { id: { type: string }, owner: { type: ref, target: App } }
entity App:
  identity: [id]
  properties: { id: { type: string } }
action Reassign:
  inputs:
    dataset: { type: ref, target: Dataset }
    target: { type: ref, target: App }
  effects:
    - dataset.owner = target
"""
    r = validate_text(text)
    assert r.ok, [d.render() for d in r.errors]
    eff = r.model.actions["Reassign"].effects[0]
    assert eff.value.kind == "path" and eff.value.segments == ["target"]


def test_parse_model_file_and_missing(tmp_path):
    f = tmp_path / "m.yaml"
    f.write_text("entity A:\n  identity: [id]\n  properties: { id: { type: string } }\n")
    model, bag = parse_model(f)
    assert "A" in model.entities and not bag.has_errors

    _, bag2 = parse_model(tmp_path / "does-not-exist.yaml")
    assert bag2.has_errors


def test_parse_model_empty_dir_warns(tmp_path):
    _, bag = parse_model(tmp_path)
    assert any(d.code == "WS-SYN-0004" for d in bag)
