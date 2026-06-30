"""RuntimeModel — an indexed, read-only view over the canonical IR.

The runtime depends on the IR (ADR-002), never on the compiler AST or raw YAML.
A RuntimeModel is built from the ``ontology.json`` of a ``.wspkg`` (or any IR
dict) and provides fast lookups the engines need.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from worldspec.runtime.errors import UnknownConstruct


@dataclass
class RuntimeModel:
    name: str
    ir_version: str
    entities: dict[str, dict] = field(default_factory=dict)
    relationships: dict[str, dict] = field(default_factory=dict)
    states: dict[str, dict] = field(default_factory=dict)
    invariants: dict[str, dict] = field(default_factory=dict)
    actions: dict[str, dict] = field(default_factory=dict)
    transitions: dict[str, dict] = field(default_factory=dict)

    # ---- construction ---------------------------------------------------- #

    @classmethod
    def from_ir(cls, ir: dict[str, Any]) -> "RuntimeModel":
        model = cls(name=ir.get("model", "model"), ir_version=ir.get("irVersion", "0"))
        buckets = {
            "entity": model.entities,
            "relationship": model.relationships,
            "state": model.states,
            "invariant": model.invariants,
            "action": model.actions,
            "transition": model.transitions,
        }
        for c in ir.get("constructs", []):
            bucket = buckets.get(c.get("kind"))
            if bucket is not None:
                bucket[c["name"]] = c
        return model

    def to_ir(self) -> dict[str, Any]:
        """Reconstruct the canonical IR document (for persistence)."""
        constructs: list[dict] = []
        for bucket in (
            self.entities, self.relationships, self.states,
            self.invariants, self.actions, self.transitions,
        ):
            constructs.extend(bucket.values())
        return {"irVersion": self.ir_version, "model": self.name, "constructs": constructs}

    # ---- derived lookups ------------------------------------------------- #

    def known_fields(self, entity_name: str) -> dict[str, dict]:
        """Properties + state dimensions declared for an entity."""
        fields: dict[str, dict] = {}
        ent = self.entities.get(entity_name)
        if ent:
            fields.update(ent.get("properties", {}))
        for st in self.states.values():
            if st.get("entity") == entity_name:
                fields.update(st.get("dimensions", {}))
        return fields

    def invariants_for_type(self, entity_name: str) -> list[dict]:
        return [i for i in self.invariants.values() if i.get("targetType") == entity_name]

    def require_transition(self, name: str) -> dict:
        if name not in self.transitions:
            raise UnknownConstruct(
                f"Transition '{name}' is not defined in model '{self.name}'. "
                f"Known: {sorted(self.transitions)}"
            )
        return self.transitions[name]

    def require_action(self, name: str) -> dict:
        if name not in self.actions:
            raise UnknownConstruct(
                f"Action '{name}' is not defined in model '{self.name}'."
            )
        return self.actions[name]
