"""Typed AST for WorldSpec v0.1.

These Pydantic models are the in-memory representation produced by the parser and
consumed by the semantic validator and IR generator. They are intentionally
*structural*: cross-construct references (e.g. a ``ref`` target, a preserved
invariant) are stored as plain names here and resolved later by the semantic
validator. Each node carries a best-effort ``line`` for diagnostics.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Shared type vocabulary
# --------------------------------------------------------------------------- #

PRIMITIVE_TYPES = {"string", "int", "float", "bool", "datetime"}
ALL_TYPES = PRIMITIVE_TYPES | {"enum", "ref"}

Scalar = Union[str, int, float, bool]


class TypeDecl(BaseModel):
    """A property / dimension / input type declaration."""

    type: str
    required: bool = False
    values: Optional[list[Scalar]] = None  # enum
    target: Optional[str] = None  # ref -> entity name
    line: Optional[int] = None


# --------------------------------------------------------------------------- #
# Invariant expression AST (§4 of the spec)
# --------------------------------------------------------------------------- #

COMPARISON_OPERATORS = {"==", "!=", "<", "<=", ">", ">="}
LOGICAL_OPERATORS = {"and", "or", "not"}
AGGREGATE_FUNCTIONS = {"count", "sum", "min", "max", "exists"}


class Literalcls(BaseModel):
    kind: Literal["literal"] = "literal"
    value: Scalar


class PathRef(BaseModel):
    kind: Literal["path"] = "path"
    path: str


class Aggregate(BaseModel):
    kind: Literal["aggregate"] = "aggregate"
    function: str
    path: str


Operand = Union[Literalcls, PathRef, Aggregate]


class Comparison(BaseModel):
    kind: Literal["comparison"] = "comparison"
    operator: str
    left: Operand
    right: Operand


class Logical(BaseModel):
    kind: Literal["logical"] = "logical"
    operator: str
    operands: list["Expr"]


Expr = Union[Comparison, Logical]


# --------------------------------------------------------------------------- #
# Action mini-language AST (§5 of the spec)
# --------------------------------------------------------------------------- #


class PathOperand(BaseModel):
    kind: Literal["path"] = "path"
    segments: list[str]

    @property
    def root(self) -> str:
        return self.segments[0]

    @property
    def text(self) -> str:
        return ".".join(self.segments)


class ValueOperand(BaseModel):
    kind: Literal["value"] = "value"
    value: Scalar


ActionOperand = Union[PathOperand, ValueOperand]


class Predicate(BaseModel):
    """A precondition: ``path <cmp> operand``."""

    raw: str
    left: PathOperand
    operator: str
    right: ActionOperand
    line: Optional[int] = None


class Assignment(BaseModel):
    """An effect / rollback step: ``path = operand``."""

    raw: str
    target: PathOperand
    value: ActionOperand
    line: Optional[int] = None


# --------------------------------------------------------------------------- #
# Core constructs
# --------------------------------------------------------------------------- #


class ConstructKind(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    STATE = "state"
    INVARIANT = "invariant"
    ACTION = "action"
    TRANSITION = "transition"


class Entity(BaseModel):
    kind: Literal[ConstructKind.ENTITY] = ConstructKind.ENTITY
    name: str
    description: Optional[str] = None
    identity: list[str] = Field(default_factory=list)
    properties: dict[str, TypeDecl] = Field(default_factory=dict)
    line: Optional[int] = None


class Relationship(BaseModel):
    kind: Literal[ConstructKind.RELATIONSHIP] = ConstructKind.RELATIONSHIP
    name: str
    from_: str = Field(alias="from")
    to: str
    cardinality: str = "many"
    temporal: bool = False
    line: Optional[int] = None

    model_config = {"populate_by_name": True}


class State(BaseModel):
    kind: Literal[ConstructKind.STATE] = ConstructKind.STATE
    name: str
    entity: str
    dimensions: dict[str, TypeDecl] = Field(default_factory=dict)
    line: Optional[int] = None


class Invariant(BaseModel):
    kind: Literal[ConstructKind.INVARIANT] = ConstructKind.INVARIANT
    name: str
    appliesTo: str
    expression: Expr
    severity: str = "warning"
    on_violation: str = "warn"
    line: Optional[int] = None


class Action(BaseModel):
    kind: Literal[ConstructKind.ACTION] = ConstructKind.ACTION
    name: str
    inputs: dict[str, TypeDecl] = Field(default_factory=dict)
    preconditions: list[Predicate] = Field(default_factory=list)
    effects: list[Assignment] = Field(default_factory=list)
    rollback: list[Assignment] = Field(default_factory=list)
    line: Optional[int] = None

    @property
    def reversible(self) -> bool:
        return len(self.rollback) > 0


class Transition(BaseModel):
    kind: Literal[ConstructKind.TRANSITION] = ConstructKind.TRANSITION
    name: str
    action: str
    from_: dict[str, Scalar] = Field(default_factory=dict, alias="from")
    to: dict[str, Scalar] = Field(default_factory=dict)
    preserves: list[str] = Field(default_factory=list)
    line: Optional[int] = None

    model_config = {"populate_by_name": True}


Construct = Union[Entity, Relationship, State, Invariant, Action, Transition]


class Model(BaseModel):
    """A whole WorldSpec model: the merged set of constructs across files."""

    name: str = "model"
    entities: dict[str, Entity] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    states: dict[str, State] = Field(default_factory=dict)
    invariants: dict[str, Invariant] = Field(default_factory=dict)
    actions: dict[str, Action] = Field(default_factory=dict)
    transitions: dict[str, Transition] = Field(default_factory=dict)

    def all_construct_names(self) -> list[str]:
        names: list[str] = []
        for bucket in (
            self.entities,
            self.relationships,
            self.states,
            self.invariants,
            self.actions,
            self.transitions,
        ):
            names.extend(bucket.keys())
        return names

    def iter_constructs(self):
        yield from self.entities.values()
        yield from self.relationships.values()
        yield from self.states.values()
        yield from self.invariants.values()
        yield from self.actions.values()
        yield from self.transitions.values()


Logical.model_rebuild()
