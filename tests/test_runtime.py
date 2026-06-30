"""Runtime tests: world services, engines, and the Milestone 2 acceptance."""

import json

import pytest
from conftest import MODELS_DIR

from worldspec.runtime import (
    RuntimeModel,
    World,
    load_model,
    simulate_from_context,
)
from worldspec.runtime.actions import ActionEngine
from worldspec.runtime.errors import EntityTypeError, RelationshipError, UnknownConstruct
from worldspec.runtime.invariants import InvariantEngine
from worldspec.runtime.transitions import TransitionEngine

APPMOD = MODELS_DIR / "application-modernization"
SWING = MODELS_DIR / "swing-legacy-assessment"
CONTEXT = MODELS_DIR.parent / "examples" / "investone-like-demo" / "context.json"


@pytest.fixture(scope="module")
def model():
    return load_model(APPMOD)


# --------------------------- world services -------------------------------- #


def test_create_entity_and_type_validation(model):
    world = World(model)
    ds = world.create_entity("Dataset", "D1", {"activeWriters": 1})
    assert ds.type == "Dataset"
    with pytest.raises(EntityTypeError):
        world.create_entity("Ghost", "G1")
    with pytest.raises(EntityTypeError):
        world.create_entity("Dataset", "D2", {"notAField": 1})


def test_relationship_cardinality_and_impact(model):
    world = World(model)
    world.create_entity("BatchJob", "J1")
    world.create_entity("Dataset", "D1")
    world.create_entity("ReportingSystem", "R1")
    world.create_relationship("writes", "J1", "D1")
    world.create_relationship("consumes", "R1", "D1")
    # scheduledBy is cardinality 'one'
    world.create_entity("Scheduler", "S1")
    world.create_entity("Scheduler", "S2")
    world.create_relationship("scheduledBy", "J1", "S1")
    with pytest.raises(RelationshipError):
        world.create_relationship("scheduledBy", "J1", "S2")
    assert world.impact("J1") == ["D1", "S1"]


def test_state_history(model):
    world = World(model)
    world.create_entity("Dataset", "D1", {"activeWriters": 1})
    world.set_state("D1", "activeWriters", 2)
    hist = world.history_for("D1")
    assert hist[-1].old == 1 and hist[-1].new == 2


# --------------------------- invariant engine ------------------------------ #


def test_invariant_aggregate_pass_and_fail(model):
    eng = InvariantEngine(model)
    inv = model.invariants["SingleWriter"]
    assert eng.evaluate_one(inv, {"activeWriters": 1}, "D1").passed
    res = eng.evaluate_one(inv, {"activeWriters": 2}, "D1")
    assert not res.passed and "VIOLATED" in res.explanation


def test_invariant_logical_not_and():
    """Exercises not(and(...)) on the Swing model's NoBlockingIoOnEDT."""
    m = load_model(SWING)
    eng = InvariantEngine(m)
    inv = m.invariants["NoBlockingIoOnEDT"]
    assert not eng.evaluate_one(inv, {"executesOn": "edt", "performsBlockingIo": True}, "h1").passed
    assert eng.evaluate_one(inv, {"executesOn": "worker", "performsBlockingIo": True}, "h2").passed


# --------------------------- action engine --------------------------------- #


def test_action_preconditions_and_effects(model):
    world = World(model)
    world.create_entity("Dataset", "D1", {"lockMode": "none", "writeAuthority": "A1"})
    world.create_entity("Application", "A1", {"validationStatus": "passed"})
    world.create_entity("Application", "A2", {"validationStatus": "passed"})
    eng = ActionEngine(model)
    bindings = {"dataset": "D1", "source": "A1", "target": "A2"}
    plan = eng.plan("TransferWriteAuthority", bindings, world)
    assert plan.preconditions_met
    assert plan.reversible
    candidate = eng.apply(plan, world)
    # effect: dataset.writeAuthority = target (A2); live world unchanged
    assert candidate.get_state("D1", "writeAuthority") == "A2"
    assert world.get_state("D1", "writeAuthority") == "A1"


# --------------------------- transition engine ----------------------------- #


def test_simulate_blocked_dual_write(model):
    ctx = json.loads(CONTEXT.read_text(encoding="utf-8"))
    result = simulate_from_context(model, ctx, actor="t", timestamp="2026-01-01T00:00:00Z")
    assert result.allowed is False
    assert result.risk_level == "critical"
    failed = {v.invariant for v in result.violations}
    assert "SingleWriter" in failed
    # safer path is derived from the model, not hard-coded
    assert result.recommended_trajectory == ["ShadowRun", "CompareOutputs", "TransferWriteAuthority"]
    ev = result.evidence
    assert "SingleWriter" in ev.invariants_failed
    assert ev.recommended_next_step == "ShadowRun"
    assert ev.decision_id.startswith("dec-")


def test_simulate_allowed_when_safe(model):
    ctx = {
        "transition": "COBOLToJava",
        "entities": {
            "D1": {"type": "Dataset", "state": {"lockMode": "none", "activeWriters": 1, "unreconciledItems": 0, "writeAuthority": "COB"}},
            "COB": {"type": "Application", "state": {"validationStatus": "passed", "rollbackWindowHours": 24}},
            "JAVA": {"type": "Application", "state": {"validationStatus": "passed", "rollbackWindowHours": 24}},
        },
        "bindings": {"dataset": "D1", "source": "COB", "target": "JAVA"},
    }
    result = simulate_from_context(model, ctx)
    assert result.allowed is True
    assert result.risk_level in ("low", "medium")
    assert result.recommended_trajectory == ["TransferWriteAuthority"]


def test_simulate_unknown_transition(model):
    with pytest.raises(UnknownConstruct):
        simulate_from_context(model, {"transition": "Nope", "bindings": {}})


# --------------------------- registry / loading ---------------------------- #


def test_load_model_from_package(tmp_path):
    from worldspec.compiler import compile_model
    from worldspec.compiler.generators import build_package
    from worldspec.runtime import load_model_from_package

    result = compile_model(APPMOD)
    pkg = tmp_path / "m.wspkg"
    build_package(result.model, result.ir, pkg)
    rt = load_model_from_package(pkg)
    assert isinstance(rt, RuntimeModel)
    assert "SingleWriter" in rt.invariants
