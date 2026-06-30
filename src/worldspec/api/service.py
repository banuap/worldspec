"""Service layer for the WorldSpec API.

All business logic lives here so the FastAPI routes stay thin (engineering
standard: keep business logic out of API routes). Wraps the runtime registry and
engines.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional

from worldspec.runtime import RuntimeModel, load_model, simulate_from_context
from worldspec.runtime.errors import RuntimeError_
from worldspec.runtime.events import Outcome, TransitionEvent
from worldspec.runtime.invariants import InvariantEngine
from worldspec.runtime.registry import ModelRegistry
from worldspec.runtime.simulate import build_world
from worldspec.runtime.store import InMemoryStore, Store


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class WorldSpecService:
    def __init__(self, store: Optional[Store] = None, models_root: Optional[Path] = None) -> None:
        self.registry = ModelRegistry()
        self.store: Store = store or InMemoryStore()
        self.models_root = Path(models_root or os.environ.get("WORLDSPEC_MODELS", Path.cwd() / "models"))
        self._evidence: dict[str, dict] = {}
        # Re-hydrate any durably-persisted packages (e.g. from `worldspec deploy`).
        for name, version, ir in self.store.load_packages():
            self.registry.register(RuntimeModel.from_ir(ir), version=version)

    # -- registration ------------------------------------------------------ #

    def register_path(self, path: str, name: Optional[str] = None, *, persist: bool = False) -> dict:
        try:
            model = load_model(path)
        except RuntimeError_ as exc:
            raise ServiceError(getattr(exc, "code", "WS-RUN-0000"), str(exc), 400)
        except Exception as exc:  # noqa: BLE001 - surface as API error
            raise ServiceError("WS-API-0001", f"Could not load model: {exc}", 400)
        if name:
            model.name = name
        self.registry.register(model)
        if persist:
            self.store.save_package(model.name, model.ir_version, model.to_ir())
        return self._model_summary(model)

    def bootstrap(self, models_root: Path) -> list[str]:
        """Register every model directory found under ``models_root``."""
        registered: list[str] = []
        if not models_root.is_dir():
            return registered
        for child in sorted(models_root.iterdir()):
            if child.is_dir() and (list(child.glob("*.yaml")) or list(child.glob("*.yml"))):
                try:
                    self.register_path(str(child))
                    registered.append(child.name)
                except ServiceError:
                    continue
        return registered

    def build_from_repo(self, repo: str, name: str, *, use_llm: bool = True, rich: bool = True) -> dict:
        """Survey a repo, generate a model, validate it, save + register if valid."""
        from worldspec.builder import build_model
        from worldspec.builder.survey import SurveyError

        try:
            result = build_model(repo, name, prefer_llm=use_llm, rich=rich)
        except SurveyError as exc:
            raise ServiceError(getattr(exc, "code", "WS-BLD-0001"), str(exc), 400)
        payload = result.to_dict()
        payload["registered"] = False
        if result.ok:
            target = self.models_root / name
            target.mkdir(parents=True, exist_ok=True)
            (target / "model.yaml").write_text(result.model_yaml, encoding="utf-8")
            if result.context is not None:
                (target / "context.json").write_text(
                    json.dumps(result.context, indent=2), encoding="utf-8"
                )
            self.register_path(str(target), name, persist=True)
            payload["registered"] = True
            payload["path"] = str(target)
        return payload

    # -- queries ----------------------------------------------------------- #

    def list_models(self) -> list[dict]:
        out = []
        for name, versions in self.registry.list_models().items():
            model = self.registry.get(name)
            summary = self._model_summary(model)
            summary["versions"] = versions
            out.append(summary)
        return out

    def get_model(self, name: str) -> dict:
        model = self._require(name)
        return {
            "name": model.name,
            "irVersion": model.ir_version,
            "entities": list(model.entities.values()),
            "relationships": list(model.relationships.values()),
            "states": list(model.states.values()),
            "invariants": list(model.invariants.values()),
            "actions": list(model.actions.values()),
            "transitions": list(model.transitions.values()),
        }

    def model_graph(self, name: str) -> dict:
        """Type-level dependency graph (entities + relationships)."""
        model = self._require(name)
        nodes = [{"id": e["name"], "kind": "entity"} for e in model.entities.values()]
        edges = [
            {"from": r["from"], "to": r["to"], "type": r["name"], "cardinality": r.get("cardinality")}
            for r in model.relationships.values()
        ]
        return {"nodes": nodes, "edges": edges}

    def transitions(self, name: str) -> list[dict]:
        model = self._require(name)
        return list(model.transitions.values())

    # -- simulation -------------------------------------------------------- #

    def simulate(self, name: str, context: dict, *, actor: Optional[str] = None, timestamp: Optional[str] = None) -> dict:
        model = self._require(name)
        try:
            result = simulate_from_context(model, context, actor=actor, timestamp=timestamp)
        except RuntimeError_ as exc:
            raise ServiceError(getattr(exc, "code", "WS-RUN-0000"), str(exc), 400)
        payload = result.to_dict()
        self._evidence[result.evidence.decision_id] = payload["evidence"]
        # Record the transition event (the ML-prerequisite ledger, §15).
        event = self._build_event(model, result, actor)
        self.store.record_event(event)
        payload["eventId"] = event.id
        return payload

    def get_evidence(self, decision_id: str) -> dict:
        if decision_id not in self._evidence:
            raise ServiceError("WS-API-0002", f"No evidence for decision '{decision_id}'", 404)
        return self._evidence[decision_id]

    # -- transition-event ledger (§15) ------------------------------------- #

    def list_events(self) -> list[dict]:
        return [e.to_dict() for e in self.store.list_events()]

    def get_event(self, event_id: str) -> dict:
        event = self.store.get_event(event_id)
        if event is None:
            raise ServiceError("WS-API-0003", f"No event '{event_id}'", 404)
        return event.to_dict()

    def record_outcome(self, event_id: str, observed_state: dict, outcome: str) -> dict:
        if outcome not in {o.value for o in Outcome}:
            raise ServiceError("WS-API-0004", f"Invalid outcome '{outcome}'", 400)
        try:
            event = self.store.set_outcome(event_id, observed_state, outcome)
        except KeyError:
            raise ServiceError("WS-API-0003", f"No event '{event_id}'", 404)
        return event.to_dict()

    def _build_event(self, model: RuntimeModel, result, actor: Optional[str]) -> TransitionEvent:
        seed = result.evidence.decision_id + json.dumps(result.state_before, sort_keys=True, default=str)
        event_id = "evt-" + hashlib.sha1(seed.encode()).hexdigest()[:12]
        return TransitionEvent(
            id=event_id,
            model=model.name,
            transition=result.transition,
            action=result.action,
            decision_id=result.evidence.decision_id,
            allowed_prediction=result.allowed,
            risk_level=result.risk_level,
            state_before=result.state_before,
            predicted_state_after=result.predicted_state_after,
            actor=actor,
            timestamp=result.evidence.timestamp,
        )

    # -- world inspection (state + impact + invariants) -------------------- #

    def inspect_world(self, name: str, context: dict) -> dict:
        model = self._require(name)
        try:
            world = build_world(model, context)
        except RuntimeError_ as exc:
            raise ServiceError(getattr(exc, "code", "WS-RUN-0000"), str(exc), 400)
        engine = InvariantEngine(model)
        entities = []
        for inst in world.entities.values():
            checks = []
            for inv in model.invariants_for_type(inst.type):
                res = engine.evaluate_one(inv, inst.state, inst.id)
                checks.append(res.to_dict())
            entities.append(
                {
                    "id": inst.id,
                    "type": inst.type,
                    "state": inst.state,
                    "impact": world.impact(inst.id),
                    "invariants": checks,
                }
            )
        edges = [{"from": r.from_id, "to": r.to_id, "type": r.name} for r in world.relationships]
        return {"entities": entities, "relationships": edges}

    def impact(self, name: str, context: dict, entity_id: str) -> dict:
        model = self._require(name)
        world = build_world(model, context)
        return {"entity": entity_id, "impacted": world.impact(entity_id)}

    # -- helpers ----------------------------------------------------------- #

    def _require(self, name: str) -> RuntimeModel:
        try:
            return self.registry.get(name)
        except RuntimeError_ as exc:
            raise ServiceError("WS-API-0404", str(exc), 404)

    @staticmethod
    def _model_summary(model: RuntimeModel) -> dict:
        return {
            "name": model.name,
            "irVersion": model.ir_version,
            "counts": {
                "entity": len(model.entities),
                "relationship": len(model.relationships),
                "state": len(model.states),
                "invariant": len(model.invariants),
                "action": len(model.actions),
                "transition": len(model.transitions),
            },
        }
