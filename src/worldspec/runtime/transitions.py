"""Transition engine (§11.7) + rule-based simulation logic (§14).

Given a transition and a bound world, it: builds a candidate future state by
applying the transition's action, checks every preserved invariant against that
candidate, computes affected entities, scores risk with an explainable weighted
formula, derives a safer trajectory from the model, and returns evidence.

Nothing here is hard-coded to any ontology (operating rule 9): the recommended
trajectory is derived by chaining the model's own actions (an action whose effect
satisfies an unmet precondition becomes a prerequisite step).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional

from worldspec.runtime.actions import ActionEngine, ActionPlan
from worldspec.runtime.evidence import Evidence
from worldspec.runtime.invariants import InvariantEngine, InvariantResult
from worldspec.runtime.model import RuntimeModel
from worldspec.runtime.world import World

_SEVERITY_WEIGHT = {"critical": 40.0, "high": 20.0, "warning": 10.0, "info": 5.0}
_RISK_BANDS = [(20.0, "low"), (40.0, "medium"), (70.0, "high")]


@dataclass
class SimulationResult:
    transition: str
    action: str
    allowed: bool
    risk_level: str
    risk_components: dict[str, float]
    violations: list[InvariantResult]
    passed: list[InvariantResult]
    impacted_entities: list[str]
    recommended_trajectory: list[str]
    evidence: Evidence
    # state captured for the transition-event ledger (§15, ML prerequisite)
    state_before: dict[str, dict] = field(default_factory=dict)
    predicted_state_after: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition": self.transition,
            "action": self.action,
            "allowed": self.allowed,
            "riskLevel": self.risk_level,
            "riskComponents": self.risk_components,
            "violations": [v.to_dict() for v in self.violations],
            "passed": [p.invariant for p in self.passed],
            "impactedEntities": self.impacted_entities,
            "recommendedTrajectory": self.recommended_trajectory,
            "stateBefore": self.state_before,
            "predictedStateAfter": self.predicted_state_after,
            "evidence": self.evidence.to_dict(),
        }


class TransitionEngine:
    def __init__(self, model: RuntimeModel) -> None:
        self.model = model
        self.actions = ActionEngine(model)
        self.invariants = InvariantEngine(model)

    def simulate(
        self,
        transition_name: str,
        bindings: dict[str, str],
        world: World,
        *,
        actor: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> SimulationResult:
        transition = self.model.require_transition(transition_name)
        action_name = transition["action"]
        preserves = transition.get("preserves", [])

        plan = self.actions.plan(action_name, bindings, world)
        candidate = self.actions.apply(plan, world)

        # Capture before/predicted state for the transition-event ledger.
        tracked = set(bindings.values()) | {c.entity_id for c in plan.effects}
        state_before = {i: dict(world.entities[i].state) for i in tracked if i in world.entities}
        predicted_after = {i: dict(candidate.entities[i].state) for i in tracked if i in candidate.entities}

        # Evaluate preserved invariants against the candidate future state.
        violations: list[InvariantResult] = []
        passed: list[InvariantResult] = []
        for inv_name in preserves:
            if inv_name not in self.model.invariants:
                continue
            for res in self.invariants.evaluate_named(inv_name, candidate):
                (passed if res.passed else violations).append(res)

        blocking = [
            v for v in violations
            if v.severity == "critical" or v.on_violation == "block_transition"
        ]
        allowed = plan.preconditions_met and not blocking

        impacted = self._impacted(plan, bindings, world)
        risk_components = self._risk(plan, violations, impacted, world)
        risk_level = self._band(risk_components, blocking)
        trajectory = self._recommend(action_name, plan, world, allowed)

        evidence = self._evidence(
            transition_name, action_name, plan, violations, passed,
            risk_components, allowed, trajectory, actor, timestamp,
        )
        return SimulationResult(
            transition=transition_name,
            action=action_name,
            allowed=allowed,
            risk_level=risk_level,
            risk_components=risk_components,
            violations=violations,
            passed=passed,
            impacted_entities=impacted,
            recommended_trajectory=trajectory,
            evidence=evidence,
            state_before=state_before,
            predicted_state_after=predicted_after,
        )

    # -- impact ------------------------------------------------------------ #

    def _impacted(self, plan: ActionPlan, bindings: dict[str, str], world: World) -> list[str]:
        touched = {c.entity_id for c in plan.effects}
        for instance_id in bindings.values():
            touched.add(instance_id)
            touched.update(world.impact(instance_id))
        return sorted(touched)

    # -- risk -------------------------------------------------------------- #

    def _risk(self, plan: ActionPlan, violations: list[InvariantResult], impacted: list[str], world: World) -> dict[str, float]:
        inv_w = sum(_SEVERITY_WEIGHT.get(v.severity, 5.0) for v in violations)
        crit = 0
        for eid in impacted:
            inst = world.entities.get(eid)
            if inst and str(inst.state.get("criticality")) in ("high", "systemic"):
                crit += 1
        return {
            "invariantViolations": round(inv_w, 2),
            "impactedCriticalEntities": float(crit * 10),
            "rollbackGap": 0.0 if plan.reversible else 20.0,
            "controlGap": 0.0,
            "uncertainty": 5.0 if plan.preconditions_met else 15.0,
        }

    def _band(self, components: dict[str, float], blocking: list[InvariantResult]) -> str:
        if blocking:
            return "critical"
        total = sum(components.values())
        for threshold, label in _RISK_BANDS:
            if total < threshold:
                return label
        return "critical"

    # -- recommended trajectory (model-driven) ----------------------------- #

    def _recommend(self, action_name: str, plan: ActionPlan, world: World, allowed: bool) -> list[str]:
        if allowed:
            return [action_name]
        unmet_fields = {p.raw and _last_field(self.model.actions[action_name], p.raw) for p in plan.unmet}
        unmet_fields.discard(None)
        ordered: list[str] = []
        visited: set[str] = set()
        self._collect_prereqs(action_name, unmet_fields, ordered, visited)
        return ordered + [action_name]

    def _collect_prereqs(self, action_name: str, only_fields, ordered: list[str], visited: set[str]) -> None:
        action = self.model.actions.get(action_name)
        if not action:
            return
        for pre in action.get("preconditions", []):
            field_ = pre["left"]["path"][-1]
            if only_fields is not None and field_ not in only_fields:
                continue
            if pre["operator"] != "==" or "value" not in pre["right"]:
                continue
            producer = self._find_producer(field_, pre["right"]["value"], exclude=action_name)
            if producer and producer not in visited:
                visited.add(producer)
                self._collect_prereqs(producer, None, ordered, visited)
                ordered.append(producer)

    def _find_producer(self, field_: str, value: Any, *, exclude: str) -> Optional[str]:
        for name, action in self.model.actions.items():
            if name == exclude:
                continue
            for eff in action.get("effects", []):
                if eff["target"]["path"][-1] == field_ and eff["value"].get("value") == value:
                    return name
        return None

    # -- evidence ---------------------------------------------------------- #

    def _evidence(self, transition, action, plan, violations, passed, risk_components, allowed, trajectory, actor, timestamp) -> Evidence:
        rules = [r.invariant for r in (violations + passed)]
        seed = f"{self.model.name}:{transition}:{sorted(p.raw for p in plan.preconditions)}"
        decision_id = "dec-" + hashlib.sha1(seed.encode()).hexdigest()[:12]
        assumptions = [
            "Aggregate paths resolving to a number are treated as pre-aggregated.",
            "Only entity/relationship instances supplied in the context are considered.",
        ]
        if not plan.preconditions_met:
            assumptions.append(
                "Unmet preconditions: " + "; ".join(p.detail for p in plan.unmet)
            )
        total = sum(risk_components.values())
        confidence = round(max(0.1, 1.0 - min(total, 100.0) / 100.0), 2)
        next_step = None if allowed else (trajectory[0] if trajectory else None)
        return Evidence(
            model=self.model.name,
            ir_version=self.model.ir_version,
            decision_id=decision_id,
            proposed_transition=transition,
            proposed_action=action,
            actor=actor,
            timestamp=timestamp,
            rules_evaluated=rules,
            invariants_passed=[p.invariant for p in passed],
            invariants_failed=[v.invariant for v in violations],
            risk_components=risk_components,
            confidence=confidence,
            assumptions=assumptions,
            recommended_next_step=next_step,
        )


def _last_field(action: dict, raw: str) -> Optional[str]:
    for pre in action.get("preconditions", []):
        if pre["raw"] == raw:
            return pre["left"]["path"][-1]
    return None
