"""Semantic validation (§9.2 of the agent instructions).

Operates on a parsed :class:`Model` and reports cross-reference problems with
``WS-SEM-####`` codes. The validator is pure and never mutates the model.
"""

from __future__ import annotations

from typing import Optional

from worldspec.compiler.ast import (
    Action,
    Aggregate,
    Comparison,
    Expr,
    Invariant,
    Logical,
    Model,
    PathRef,
    State,
)
from worldspec.diagnostics import DiagnosticBag, suggest


def validate_semantics(model: Model, bag: DiagnosticBag) -> None:
    entities = set(model.entities)

    _check_entities(model, entities, bag)
    _check_relationships(model, entities, bag)
    _check_states(model, entities, bag)
    _check_invariants(model, entities, bag)
    _check_actions(model, entities, bag)
    _check_transitions(model, bag)


# --------------------------------------------------------------------------- #


def _check_entities(model: Model, entities: set[str], bag: DiagnosticBag) -> None:
    for ent in model.entities.values():
        for ident in ent.identity:
            if ident not in ent.properties:
                bag.error(
                    "WS-SEM-0010",
                    f"entity {ent.name} identity references undeclared property "
                    f"'{ident}'.",
                    line=ent.line,
                    suggestion=suggest(ident, ent.properties),
                )
        for pname, prop in ent.properties.items():
            if prop.type == "ref" and prop.target not in entities:
                bag.error(
                    "WS-SEM-0001",
                    f"property '{pname}' of entity {ent.name} references unknown "
                    f"entity '{prop.target}'.",
                    line=prop.line or ent.line,
                    suggestion=suggest(str(prop.target), entities),
                )


def _check_relationships(model: Model, entities: set[str], bag: DiagnosticBag) -> None:
    for rel in model.relationships.values():
        for side, value in (("from", rel.from_), ("to", rel.to)):
            if value not in entities:
                bag.error(
                    "WS-SEM-0002",
                    f"relationship {rel.name} '{side}' references unknown entity "
                    f"'{value}'.",
                    line=rel.line,
                    suggestion=suggest(value, entities),
                )


def _check_states(model: Model, entities: set[str], bag: DiagnosticBag) -> None:
    for st in model.states.values():
        if st.entity not in entities:
            bag.error(
                "WS-SEM-0020",
                f"state {st.name} references unknown entity '{st.entity}'.",
                line=st.line,
                suggestion=suggest(st.entity, entities),
            )
        for dname, dim in st.dimensions.items():
            if dim.type == "ref" and dim.target not in entities:
                bag.error(
                    "WS-SEM-0001",
                    f"dimension '{dname}' of state {st.name} references unknown "
                    f"entity '{dim.target}'.",
                    line=dim.line or st.line,
                    suggestion=suggest(str(dim.target), entities),
                )


def _check_invariants(model: Model, entities: set[str], bag: DiagnosticBag) -> None:
    # Build per-entity known paths (properties + state dimensions) for soft checks.
    paths_by_entity = _paths_by_entity(model)
    for inv in model.invariants.values():
        if inv.appliesTo not in entities:
            bag.error(
                "WS-SEM-0021",
                f"invariant {inv.name} appliesTo unknown entity "
                f"'{inv.appliesTo}'.",
                line=inv.line,
                suggestion=suggest(inv.appliesTo, entities),
            )
            continue
        known = paths_by_entity.get(inv.appliesTo, set())
        _check_expr_paths(inv, inv.expression, known, bag)


def _check_actions(model: Model, entities: set[str], bag: DiagnosticBag) -> None:
    # Map entity -> set of state-dimension names (effects/preconditions target these).
    dims_by_entity = _dims_by_entity(model)
    for act in model.actions.values():
        # input ref targets must exist
        input_entities: dict[str, Optional[str]] = {}
        for iname, decl in act.inputs.items():
            input_entities[iname] = decl.target if decl.type == "ref" else None
            if decl.type == "ref" and decl.target not in entities:
                bag.error(
                    "WS-SEM-0030",
                    f"action {act.name} input '{iname}' references unknown entity "
                    f"'{decl.target}'.",
                    line=decl.line or act.line,
                    suggestion=suggest(str(decl.target), entities),
                )
        roots = set(act.inputs)
        for pred in act.preconditions:
            _check_action_path(act, pred.left.segments, roots, input_entities, dims_by_entity, bag)
            if pred.right.kind == "path":
                _check_action_path(act, pred.right.segments, roots, input_entities, dims_by_entity, bag)
        for eff in act.effects + act.rollback:
            _check_action_path(act, eff.target.segments, roots, input_entities, dims_by_entity, bag, is_effect=True)
            if eff.value.kind == "path":
                _check_action_path(act, eff.value.segments, roots, input_entities, dims_by_entity, bag)
        if not act.reversible:
            bag.warning(
                "WS-SEM-0032",
                f"action {act.name} declares no rollback; it will be treated as "
                "irreversible.",
                line=act.line,
            )


def _check_transitions(model: Model, bag: DiagnosticBag) -> None:
    for tr in model.transitions.values():
        if tr.action not in model.actions:
            bag.error(
                "WS-SEM-0040",
                f"transition {tr.name} references unknown action '{tr.action}'.",
                line=tr.line,
                suggestion=suggest(tr.action, model.actions),
            )
        for inv in tr.preserves:
            if inv not in model.invariants:
                bag.error(
                    "WS-SEM-0042",
                    f"transition {tr.name} references unknown invariant "
                    f"'{inv}'.",
                    line=tr.line,
                    suggestion=suggest(inv, model.invariants),
                )


# --------------------------------------------------------------------------- #
# Path helpers
# --------------------------------------------------------------------------- #


def _paths_by_entity(model: Model) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for ent in model.entities.values():
        out.setdefault(ent.name, set()).update(ent.properties)
    for st in model.states.values():
        out.setdefault(st.entity, set()).update(st.dimensions)
    return out


def _dims_by_entity(model: Model) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for st in model.states.values():
        out.setdefault(st.entity, set()).update(st.dimensions)
    for ent in model.entities.values():
        out.setdefault(ent.name, set()).update(ent.properties)
    return out


def _check_expr_paths(inv: Invariant, expr: Expr, known: set[str], bag: DiagnosticBag) -> None:
    if isinstance(expr, Logical):
        for sub in expr.operands:
            _check_expr_paths(inv, sub, known, bag)
        return
    if isinstance(expr, Comparison):
        for operand in (expr.left, expr.right):
            if isinstance(operand, (PathRef, Aggregate)):
                head = operand.path.split(".")[0]
                if known and head not in known:
                    bag.warning(
                        "WS-SEM-0050",
                        f"invariant {inv.name} references path '{operand.path}' "
                        f"not declared on entity {inv.appliesTo}.",
                        line=inv.line,
                        suggestion=suggest(head, known),
                    )


def _check_action_path(
    act: Action,
    segments: list[str],
    roots: set[str],
    input_entities: dict[str, Optional[str]],
    dims_by_entity: dict[str, set[str]],
    bag: DiagnosticBag,
    *,
    is_effect: bool = False,
) -> None:
    head = segments[0]
    if head not in roots:
        bag.error(
            "WS-SEM-0031",
            f"action {act.name} references '{'.'.join(segments)}' whose root "
            f"'{head}' is not a declared input.",
            line=act.line,
            suggestion=suggest(head, roots),
        )
        return
    # If the input is a typed ref and we know the target entity, the second
    # segment (if any) should be a property/dimension of that entity.
    if len(segments) >= 2:
        target_entity = input_entities.get(head)
        if target_entity:
            known = dims_by_entity.get(target_entity, set())
            if known and segments[1] not in known:
                bag.warning(
                    "WS-SEM-0033",
                    f"action {act.name} references '{'.'.join(segments)}' but "
                    f"'{segments[1]}' is not a known field of {target_entity}.",
                    line=act.line,
                    suggestion=suggest(segments[1], known),
                )
