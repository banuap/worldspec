"""Targeted coverage for the expression evaluator and the model registry."""

import pytest
from conftest import MODELS_DIR

from worldspec.runtime import RuntimeModel, load_model
from worldspec.runtime.errors import ModelNotFound
from worldspec.runtime.expressions import evaluate
from worldspec.runtime.registry import ModelRegistry

APPMOD = MODELS_DIR / "application-modernization"


# --------------------------- expression evaluator ------------------------- #


def cmp(op, left, right):
    return evaluate({"operator": op, "left": {"path": "x"}, "right": right}, {"x": left})


def test_comparators():
    assert cmp("==", 1, 1) and not cmp("==", 1, 2)
    assert cmp("!=", 1, 2)
    assert cmp("<", 1, 2) and cmp("<=", 2, 2)
    assert cmp(">", 3, 2) and cmp(">=", 2, 2)


def test_ordering_against_missing_state_is_violation():
    # path resolves to None -> ordering comparison cannot hold
    assert evaluate({"operator": "<=", "left": {"path": "missing"}, "right": 1}, {}) is False


def test_logical_or_and_not():
    expr = {
        "operator": "or",
        "operands": [
            {"operator": "==", "left": {"path": "a"}, "right": 1},
            {"operator": "==", "left": {"path": "b"}, "right": 2},
        ],
    }
    assert evaluate(expr, {"a": 9, "b": 2})  # second branch true
    assert not evaluate(expr, {"a": 9, "b": 9})
    not_expr = {"operator": "not", "operands": [{"operator": "==", "left": {"path": "a"}, "right": 1}]}
    assert evaluate(not_expr, {"a": 2})


def test_aggregates_over_list_and_scalar():
    def agg(fn, val, op, rhs):
        return evaluate(
            {"operator": op, "left": {"function": fn, "path": "p"}, "right": rhs}, {"p": val}
        )

    assert agg("count", [1, 2, 3], "==", 3)
    assert agg("sum", [1, 2, 3], "==", 6)
    assert agg("min", [3, 1, 2], "==", 1)
    assert agg("max", [3, 1, 2], "==", 3)
    assert agg("exists", [1], "==", True)
    assert agg("exists", [], "==", False)
    # scalar treated as pre-aggregated
    assert agg("count", 2, "<=", 1) is False
    assert agg("count", 2, "==", 2)


# --------------------------- model registry ------------------------------- #


def test_registry_register_activate_get_list():
    reg = ModelRegistry()
    m = load_model(APPMOD)
    reg.register(m, version="0.1.0")
    reg.register(m, version="0.2.0", activate=False)
    assert reg.get(m.name).ir_version == "0.1.0"  # active stays 0.1.0
    reg.activate(m.name, "0.2.0")
    assert reg.get(m.name) is m
    listing = reg.list_models()
    assert listing[m.name] == ["0.1.0", "0.2.0"]


def test_registry_errors():
    reg = ModelRegistry()
    with pytest.raises(ModelNotFound):
        reg.get("nope")
    m = load_model(APPMOD)
    reg.register(m)
    with pytest.raises(ModelNotFound):
        reg.activate(m.name, "9.9.9")
    with pytest.raises(ModelNotFound):
        reg.get(m.name, "9.9.9")


def test_registry_package_not_found(tmp_path):
    reg = ModelRegistry()
    with pytest.raises(ModelNotFound):
        reg.register_package(tmp_path / "missing.wspkg")
