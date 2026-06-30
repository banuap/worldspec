"""WorldSpec runtime (Milestone 2).

Loads a compiled model (the canonical IR), holds typed entity/relationship/state
instances, and runs the invariant, action, and transition engines to simulate a
proposed change and return explainable evidence. Depends only on the IR
(ADR-002/003); never on raw YAML and never uses ``eval`` (ADR-005).
"""

from worldspec.runtime.model import RuntimeModel
from worldspec.runtime.registry import (
    ModelRegistry,
    load_ir_from_package,
    load_model_from_package,
)
from worldspec.runtime.simulate import (
    build_world,
    load_model,
    simulate_from_context,
)
from worldspec.runtime.transitions import SimulationResult, TransitionEngine
from worldspec.runtime.world import World

__all__ = [
    "RuntimeModel",
    "ModelRegistry",
    "load_ir_from_package",
    "load_model_from_package",
    "load_model",
    "build_world",
    "simulate_from_context",
    "SimulationResult",
    "TransitionEngine",
    "World",
]
