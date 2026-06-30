"""Action engine (§11.6).

Validates action inputs, checks preconditions against the world, computes the
proposed effects, and produces a reversible execution plan. Effects are applied
to a *candidate* world, never the live one, until a transition is accepted.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any, Optional

from worldspec.runtime.errors import BindingError
from worldspec.runtime.model import RuntimeModel
from worldspec.runtime.world import World

_COMPARATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass
class PreconditionResult:
    raw: str
    satisfied: bool
    detail: str


@dataclass
class EffectChange:
    entity_id: str
    field: str
    old: Any
    new: Any


@dataclass
class ActionPlan:
    action: str
    preconditions: list[PreconditionResult]
    effects: list[EffectChange]
    reversible: bool

    @property
    def preconditions_met(self) -> bool:
        return all(p.satisfied for p in self.preconditions)

    @property
    def unmet(self) -> list[PreconditionResult]:
        return [p for p in self.preconditions if not p.satisfied]


class ActionEngine:
    def __init__(self, model: RuntimeModel) -> None:
        self.model = model

    # -- path resolution --------------------------------------------------- #

    def _resolve(self, segments: list[str], bindings: dict[str, str], world: World) -> Any:
        root = segments[0]
        if root not in bindings:
            raise BindingError(f"No binding for action input '{root}'")
        instance_id = bindings[root]
        if len(segments) == 1:
            # a bare input reference resolves to the bound instance id
            return instance_id
        inst = world.get_entity(instance_id)
        value: Any = inst.state
        for seg in segments[1:]:
            value = value.get(seg) if isinstance(value, dict) else None
        return value

    def _operand_value(self, operand: dict, bindings: dict[str, str], world: World) -> Any:
        if "value" in operand:
            return operand["value"]
        if "path" in operand:
            return self._resolve(operand["path"], bindings, world)
        raise BindingError(f"malformed operand {operand!r}")

    # -- preconditions ----------------------------------------------------- #

    def check_preconditions(self, action: dict, bindings: dict[str, str], world: World) -> list[PreconditionResult]:
        results: list[PreconditionResult] = []
        for pre in action.get("preconditions", []):
            left = self._resolve(pre["left"]["path"], bindings, world)
            right = self._operand_value(pre["right"], bindings, world)
            cmp = _COMPARATORS[pre["operator"]]
            try:
                ok = bool(cmp(left, right)) if not (left is None and pre["operator"] not in ("==", "!=")) else False
            except TypeError:
                ok = False
            results.append(
                PreconditionResult(
                    raw=pre["raw"],
                    satisfied=ok,
                    detail=f"{'.'.join(pre['left']['path'])}={left!r} {pre['operator']} {right!r}",
                )
            )
        return results

    # -- effects ----------------------------------------------------------- #

    def plan(self, action_name: str, bindings: dict[str, str], world: World) -> ActionPlan:
        action = self.model.require_action(action_name)
        self._validate_bindings(action, bindings, world)
        pres = self.check_preconditions(action, bindings, world)
        effects: list[EffectChange] = []
        for eff in action.get("effects", []):
            segments = eff["target"]["path"]
            instance_id = bindings[segments[0]]
            field_ = segments[1] if len(segments) > 1 else segments[0]
            new = self._operand_value(eff["value"], bindings, world)
            old = world.get_state(instance_id, field_)
            effects.append(EffectChange(entity_id=instance_id, field=field_, old=old, new=new))
        return ActionPlan(
            action=action_name,
            preconditions=pres,
            effects=effects,
            reversible=bool(action.get("reversible")),
        )

    def apply(self, plan: ActionPlan, world: World) -> World:
        """Apply a plan's effects to a *candidate* snapshot of the world."""
        candidate = world.snapshot()
        for change in plan.effects:
            candidate.set_state(change.entity_id, change.field, change.new)
        return candidate

    def _validate_bindings(self, action: dict, bindings: dict[str, str], world: World) -> None:
        for name, decl in action.get("inputs", {}).items():
            if name not in bindings:
                raise BindingError(f"action '{action['name']}' input '{name}' is unbound")
            inst = world.get_entity(bindings[name])
            target = decl.get("target")
            if decl.get("type") == "ref" and target and inst.type != target:
                raise BindingError(
                    f"input '{name}' expects {target}, bound to {inst.type} '{inst.id}'"
                )
