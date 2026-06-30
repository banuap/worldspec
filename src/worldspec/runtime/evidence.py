"""Evidence service (§11.8, ADR-008).

Every simulation returns an evidence record so decisions are explainable: which
model/version, what was proposed, which rules were evaluated and passed/failed,
the risk breakdown, assumptions, confidence, and the recommended next step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Evidence:
    model: str
    ir_version: str
    decision_id: str
    proposed_transition: str
    proposed_action: str
    actor: Optional[str]
    timestamp: Optional[str]
    rules_evaluated: list[str]
    invariants_passed: list[str]
    invariants_failed: list[str]
    risk_components: dict[str, float]
    confidence: float
    assumptions: list[str]
    recommended_next_step: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisionId": self.decision_id,
            "model": self.model,
            "irVersion": self.ir_version,
            "proposedTransition": self.proposed_transition,
            "proposedAction": self.proposed_action,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "rulesEvaluated": self.rules_evaluated,
            "invariantsPassed": self.invariants_passed,
            "invariantsFailed": self.invariants_failed,
            "riskComponents": self.risk_components,
            "confidence": self.confidence,
            "assumptions": self.assumptions,
            "recommendedNextStep": self.recommended_next_step,
        }
