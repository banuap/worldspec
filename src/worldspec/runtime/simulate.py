"""Simulation orchestrator — turn a context document into a SimulationResult.

A *context* describes the observed world for one simulation:

```json
{
  "transition": "COBOLToJava",
  "entities": {
    "SETTLEMENT.VSAM": {"type": "Dataset", "state": {"activeWriters": 2, "lockMode": "none"}},
    "GS-COBOL":  {"type": "Application", "state": {"validationStatus": "passed"}},
    "GS-Java":   {"type": "Application", "state": {"validationStatus": "pending", "lifecycle": "active"}}
  },
  "relationships": [{"name": "writes", "from": "JOB.SETTLE.020", "to": "SETTLEMENT.VSAM"}],
  "bindings": {"dataset": "SETTLEMENT.VSAM", "source": "GS-COBOL", "target": "GS-Java"}
}
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from worldspec.runtime.errors import SimulationError
from worldspec.runtime.model import RuntimeModel
from worldspec.runtime.registry import load_model_from_package
from worldspec.runtime.transitions import SimulationResult, TransitionEngine
from worldspec.runtime.world import World


def build_world(model: RuntimeModel, context: dict[str, Any]) -> World:
    world = World(model)
    for inst_id, spec in context.get("entities", {}).items():
        if "type" not in spec:
            raise SimulationError(f"context entity '{inst_id}' is missing 'type'")
        world.create_entity(spec["type"], inst_id, spec.get("state", {}))
    for rel in context.get("relationships", []):
        world.create_relationship(rel["name"], rel["from"], rel["to"])
    return world


def simulate_from_context(
    model: RuntimeModel,
    context: dict[str, Any],
    *,
    actor: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> SimulationResult:
    if "transition" not in context:
        raise SimulationError("context is missing 'transition'")
    if "bindings" not in context:
        raise SimulationError("context is missing 'bindings'")
    world = build_world(model, context)
    engine = TransitionEngine(model)
    return engine.simulate(
        context["transition"], context["bindings"], world, actor=actor, timestamp=timestamp
    )


def load_model(path: str | Path) -> RuntimeModel:
    """Load a RuntimeModel from a .wspkg, or compile a model dir/file on the fly."""
    p = Path(path)
    if not p.exists():
        raise SimulationError(
            f"model path not found: {p.resolve()} "
            "(run from the repo root, or pass an absolute --model path)"
        )
    if p.suffix == ".wspkg":
        return load_model_from_package(p)
    # Convenience: compile a source model directory/file via the compiler.
    from worldspec.compiler import compile_model  # local import keeps core independent

    result = compile_model(p)
    if not result.ok:
        raise SimulationError(
            f"model at {p} does not compile ({len(result.errors)} error(s)); "
            "run `worldspec validate` first"
        )
    return RuntimeModel.from_ir(result.ir)
