"""Transition-event ledger (§15 / ADR-007).

The learned (JEPA-style) world model must not be trained until the runtime
records, for every transition it simulates/executes:

    state_before, action, predicted_state_after, observed_state_after,
    outcome, prediction_error

This module defines that record and how prediction error is computed once an
observed outcome is supplied. Capturing these events is the prerequisite that
unblocks the ML roadmap; it is not itself ML.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Outcome(str, Enum):
    PENDING = "pending"      # simulated, no observed result yet
    SUCCESS = "success"      # the change was applied and held
    FAILURE = "failure"      # the change was applied and broke something
    ROLLED_BACK = "rolled_back"


@dataclass
class TransitionEvent:
    id: str
    model: str
    transition: str
    action: str
    decision_id: str
    allowed_prediction: bool
    risk_level: str
    state_before: dict[str, dict]
    predicted_state_after: dict[str, dict]
    observed_state_after: Optional[dict[str, dict]] = None
    outcome: str = Outcome.PENDING.value
    prediction_error: Optional[dict[str, Any]] = None
    actor: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "transition": self.transition,
            "action": self.action,
            "decisionId": self.decision_id,
            "allowedPrediction": self.allowed_prediction,
            "riskLevel": self.risk_level,
            "stateBefore": self.state_before,
            "predictedStateAfter": self.predicted_state_after,
            "observedStateAfter": self.observed_state_after,
            "outcome": self.outcome,
            "predictionError": self.prediction_error,
            "actor": self.actor,
            "timestamp": self.timestamp,
        }


def prediction_error(
    predicted: dict[str, dict], observed: dict[str, dict]
) -> dict[str, Any]:
    """Compare predicted vs observed state; return an explainable error record.

    The error rate is ``mismatched_fields / compared_fields`` over the fields the
    runtime predicted. Each mismatch is listed so the divergence is auditable
    (and, later, learnable).
    """
    mismatches: list[dict[str, Any]] = []
    compared = 0
    for entity_id, fields in predicted.items():
        obs_fields = observed.get(entity_id, {})
        for field_name, predicted_value in fields.items():
            compared += 1
            observed_value = obs_fields.get(field_name)
            if observed_value != predicted_value:
                mismatches.append(
                    {
                        "entity": entity_id,
                        "field": field_name,
                        "predicted": predicted_value,
                        "observed": observed_value,
                    }
                )
    rate = round(len(mismatches) / compared, 4) if compared else 0.0
    return {
        "comparedFields": compared,
        "mismatchCount": len(mismatches),
        "errorRate": rate,
        "mismatches": mismatches,
    }
