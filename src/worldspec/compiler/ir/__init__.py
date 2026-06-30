"""Canonical intermediate representation (IR) generation (§9.3).

Every construct is compiled to a neutral, JSON-serializable dict with a ``kind``
discriminator. The (future) runtime depends on this IR, never on raw YAML
(ADR-002).
"""

from __future__ import annotations

from typing import Any

from worldspec import IR_VERSION
from worldspec.compiler.ast import (
    Action,
    Aggregate,
    Assignment,
    Comparison,
    Entity,
    Expr,
    Invariant,
    Literalcls,
    Logical,
    Model,
    PathOperand,
    PathRef,
    Predicate,
    Relationship,
    State,
    Transition,
    TypeDecl,
    ValueOperand,
)


def model_to_ir(model: Model) -> dict[str, Any]:
    """Compile a whole model into the canonical IR document."""
    constructs: list[dict[str, Any]] = []
    constructs.extend(_entity_ir(e) for e in model.entities.values())
    constructs.extend(_relationship_ir(r) for r in model.relationships.values())
    constructs.extend(_state_ir(s) for s in model.states.values())
    constructs.extend(_invariant_ir(i) for i in model.invariants.values())
    constructs.extend(_action_ir(a) for a in model.actions.values())
    constructs.extend(_transition_ir(t) for t in model.transitions.values())
    return {
        "irVersion": IR_VERSION,
        "model": model.name,
        "constructs": constructs,
    }


def _type_decl_ir(td: TypeDecl) -> dict[str, Any]:
    out: dict[str, Any] = {"type": td.type}
    if td.required:
        out["required"] = True
    if td.values is not None:
        out["values"] = list(td.values)
    if td.target is not None:
        out["target"] = td.target
    return out


def _entity_ir(e: Entity) -> dict[str, Any]:
    return {
        "kind": "entity",
        "name": e.name,
        "description": e.description,
        "identity": list(e.identity),
        "properties": {k: _type_decl_ir(v) for k, v in e.properties.items()},
    }


def _relationship_ir(r: Relationship) -> dict[str, Any]:
    return {
        "kind": "relationship",
        "name": r.name,
        "from": r.from_,
        "to": r.to,
        "cardinality": r.cardinality,
        "temporal": r.temporal,
    }


def _state_ir(s: State) -> dict[str, Any]:
    return {
        "kind": "state",
        "name": s.name,
        "entity": s.entity,
        "dimensions": {k: _type_decl_ir(v) for k, v in s.dimensions.items()},
    }


def _expr_ir(expr: Expr) -> dict[str, Any]:
    if isinstance(expr, Logical):
        return {
            "operator": expr.operator,
            "operands": [_expr_ir(o) for o in expr.operands],
        }
    if isinstance(expr, Comparison):
        return {
            "operator": expr.operator,
            "left": _operand_ir(expr.left),
            "right": _operand_ir(expr.right),
        }
    raise TypeError(f"unknown expression node: {expr!r}")  # pragma: no cover


def _operand_ir(operand: Any) -> Any:
    if isinstance(operand, Literalcls):
        return operand.value
    if isinstance(operand, PathRef):
        return {"path": operand.path}
    if isinstance(operand, Aggregate):
        return {"function": operand.function, "path": operand.path}
    raise TypeError(f"unknown operand: {operand!r}")  # pragma: no cover


def _invariant_ir(i: Invariant) -> dict[str, Any]:
    return {
        "kind": "invariant",
        "name": i.name,
        "targetType": i.appliesTo,
        "expression": _expr_ir(i.expression),
        "severity": i.severity,
        "onViolation": i.on_violation,
    }


def _action_operand_ir(op: Any) -> Any:
    if isinstance(op, ValueOperand):
        return {"value": op.value}
    if isinstance(op, PathOperand):
        return {"path": op.segments}
    raise TypeError(f"unknown action operand: {op!r}")  # pragma: no cover


def _predicate_ir(p: Predicate) -> dict[str, Any]:
    return {
        "raw": p.raw,
        "left": {"path": p.left.segments},
        "operator": p.operator,
        "right": _action_operand_ir(p.right),
    }


def _assignment_ir(a: Assignment) -> dict[str, Any]:
    return {
        "raw": a.raw,
        "target": {"path": a.target.segments},
        "value": _action_operand_ir(a.value),
    }


def _action_ir(a: Action) -> dict[str, Any]:
    return {
        "kind": "action",
        "name": a.name,
        "inputs": {k: _type_decl_ir(v) for k, v in a.inputs.items()},
        "preconditions": [_predicate_ir(p) for p in a.preconditions],
        "effects": [_assignment_ir(e) for e in a.effects],
        "rollback": [_assignment_ir(r) for r in a.rollback],
        "reversible": a.reversible,
    }


def _transition_ir(t: Transition) -> dict[str, Any]:
    return {
        "kind": "transition",
        "name": t.name,
        "action": t.action,
        "from": dict(t.from_),
        "to": dict(t.to),
        "preserves": list(t.preserves),
    }
