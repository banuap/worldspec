"""The runtime world: typed entity/relationship/state instances + services.

This is the v0.1 in-memory implementation of the Entity (§11.2), Relationship
(§11.3), and State (§11.4) services. Persistence would sit behind the same
service API (ADR-004); nothing here is store-specific.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from worldspec.runtime.errors import (
    EntityTypeError,
    IdentityError,
    RelationshipError,
)
from worldspec.runtime.model import RuntimeModel


@dataclass
class EntityInstance:
    id: str
    type: str
    # properties + state dimensions live together as the instance's observable state
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationshipInstance:
    name: str  # the relationship type, e.g. "writes"
    from_id: str
    to_id: str


@dataclass
class StateChange:
    """One recorded mutation (a minimal nod to bitemporal history, ADR-006)."""

    entity_id: str
    field: str
    old: Any
    new: Any
    seq: int


class World:
    """Holds the current instances and their mutation history."""

    def __init__(self, model: RuntimeModel) -> None:
        self.model = model
        self.entities: dict[str, EntityInstance] = {}
        self.relationships: list[RelationshipInstance] = []
        self.history: list[StateChange] = []
        self._seq = 0

    # -- Entity service (§11.2) ------------------------------------------- #

    def create_entity(self, type_: str, id_: str, state: Optional[dict] = None) -> EntityInstance:
        if type_ not in self.model.entities:
            raise EntityTypeError(
                f"Unknown entity type '{type_}'. Known: {sorted(self.model.entities)}"
            )
        ent_def = self.model.entities[type_]
        # Identity properties must be present (here the instance id stands in for
        # single-key identity; declared identity props are validated if supplied).
        known = self.model.known_fields(type_)
        state = dict(state or {})
        for key in state:
            if key not in known:
                raise EntityTypeError(
                    f"{type_} has no field '{key}'. Known: {sorted(known)}"
                )
        identity = ent_def.get("identity", [])
        for key in identity:
            # identity may be carried by the instance id; only error if explicitly null
            if key in state and state[key] in (None, ""):
                raise IdentityError(f"{type_} identity field '{key}' must not be empty")
        inst = EntityInstance(id=id_, type=type_, state=state)
        self.entities[id_] = inst
        return inst

    def get_entity(self, id_: str) -> EntityInstance:
        if id_ not in self.entities:
            raise EntityTypeError(f"No entity instance '{id_}'")
        return self.entities[id_]

    def instances_of(self, type_: str) -> list[EntityInstance]:
        return [e for e in self.entities.values() if e.type == type_]

    # -- State service (§11.4) -------------------------------------------- #

    def set_state(self, id_: str, field_: str, value: Any) -> None:
        inst = self.get_entity(id_)
        old = inst.state.get(field_)
        inst.state[field_] = value
        self._seq += 1
        self.history.append(
            StateChange(entity_id=id_, field=field_, old=old, new=value, seq=self._seq)
        )

    def get_state(self, id_: str, field_: str) -> Any:
        return self.get_entity(id_).state.get(field_)

    def history_for(self, id_: str) -> list[StateChange]:
        return [h for h in self.history if h.entity_id == id_]

    # -- Relationship service (§11.3) ------------------------------------- #

    def create_relationship(self, name: str, from_id: str, to_id: str) -> RelationshipInstance:
        rel_def = self.model.relationships.get(name)
        if rel_def is None:
            raise RelationshipError(f"Unknown relationship type '{name}'")
        src, dst = self.get_entity(from_id), self.get_entity(to_id)
        if src.type != rel_def["from"]:
            raise RelationshipError(
                f"relationship {name} expects 'from' {rel_def['from']}, got {src.type}"
            )
        if dst.type != rel_def["to"]:
            raise RelationshipError(
                f"relationship {name} expects 'to' {rel_def['to']}, got {dst.type}"
            )
        if rel_def.get("cardinality") == "one":
            existing = [r for r in self.relationships if r.name == name and r.from_id == from_id]
            if existing:
                raise RelationshipError(
                    f"relationship {name} has cardinality 'one' but '{from_id}' "
                    "already has an edge"
                )
        rel = RelationshipInstance(name=name, from_id=from_id, to_id=to_id)
        self.relationships.append(rel)
        return rel

    def impact(self, entity_id: str, *, max_depth: int = 5) -> list[str]:
        """Downstream entities reachable from ``entity_id`` (impact traversal)."""
        seen: set[str] = set()
        frontier = [(entity_id, 0)]
        while frontier:
            node, depth = frontier.pop()
            if depth >= max_depth:
                continue
            for r in self.relationships:
                if r.from_id == node and r.to_id not in seen:
                    seen.add(r.to_id)
                    frontier.append((r.to_id, depth + 1))
        return sorted(seen)

    # -- candidate worlds -------------------------------------------------- #

    def snapshot(self) -> "World":
        """Deep-copy the world (used to compute candidate future states)."""
        clone = World(self.model)
        clone.entities = {k: EntityInstance(v.id, v.type, copy.deepcopy(v.state)) for k, v in self.entities.items()}
        clone.relationships = list(self.relationships)
        clone._seq = self._seq
        return clone
