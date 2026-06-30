"""Invariant engine (§11.5).

Evaluates an invariant against current or simulated state, classifies severity,
and explains the result. Produces machine- and human-readable findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from worldspec.runtime import expressions
from worldspec.runtime.model import RuntimeModel
from worldspec.runtime.world import World


@dataclass
class InvariantResult:
    invariant: str
    target_type: str
    severity: str
    passed: bool
    instance_id: Optional[str]
    on_violation: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant": self.invariant,
            "targetType": self.target_type,
            "severity": self.severity,
            "passed": self.passed,
            "instance": self.instance_id,
            "onViolation": self.on_violation,
            "reason": self.explanation,
        }


class InvariantEngine:
    def __init__(self, model: RuntimeModel) -> None:
        self.model = model

    def evaluate_one(self, invariant: dict, instance_state: dict, instance_id: Optional[str]) -> InvariantResult:
        passed = expressions.evaluate(invariant["expression"], instance_state)
        return InvariantResult(
            invariant=invariant["name"],
            target_type=invariant["targetType"],
            severity=invariant.get("severity", "warning"),
            passed=passed,
            instance_id=instance_id,
            on_violation=invariant.get("onViolation", "warn"),
            explanation=self._explain(invariant, instance_state, passed, instance_id),
        )

    def evaluate_in_world(self, invariant: dict, world: World) -> list[InvariantResult]:
        """Evaluate one invariant against every instance of its target type."""
        results = []
        for inst in world.instances_of(invariant["targetType"]):
            results.append(self.evaluate_one(invariant, inst.state, inst.id))
        if not results:
            # No instances to check: the invariant vacuously holds.
            results.append(self.evaluate_one(invariant, {}, None))
        return results

    def evaluate_named(self, name: str, world: World) -> list[InvariantResult]:
        inv = self.model.invariants[name]
        return self.evaluate_in_world(inv, world)

    @staticmethod
    def _explain(invariant: dict, state: dict, passed: bool, instance_id: Optional[str]) -> str:
        who = f"instance '{instance_id}'" if instance_id else "the target type"
        expr = _render_expr(invariant["expression"], state)
        verdict = "holds" if passed else "is VIOLATED"
        return f"{invariant['name']} {verdict} for {who}: {expr}"


def _render_expr(expr: dict, state: dict) -> str:
    """Human-readable expression with resolved values for diagnostics."""
    if "operands" in expr:
        joined = f" {expr['operator']} ".join(_render_expr(o, state) for o in expr["operands"])
        return f"({joined})"
    left = _render_operand(expr["left"], state)
    right = _render_operand(expr["right"], state)
    return f"{left} {expr['operator']} {right}"


def _render_operand(operand: Any, state: dict) -> str:
    if isinstance(operand, dict):
        if "function" in operand:
            val = expressions._eval_operand(operand, state)
            return f"{operand['function']}({operand['path']})={val}"
        if "path" in operand:
            val = expressions._resolve_path(operand["path"], state)
            return f"{operand['path']}={val!r}"
    return repr(operand)
