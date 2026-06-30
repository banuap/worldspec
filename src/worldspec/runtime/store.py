"""Persistence interfaces (ADR-004).

The runtime talks to storage only through these abstractions, so the durable
backend is swappable. v0.1 ships an in-memory store (default) and a stdlib
SQLite store (durable, zero-infra). A Neo4j/PostgreSQL store would implement the
same ``Store`` interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from worldspec.runtime.events import Outcome, TransitionEvent, prediction_error


class Store(ABC):
    """Durable storage for registered packages and transition events."""

    # -- packages ---------------------------------------------------------- #

    @abstractmethod
    def save_package(self, name: str, version: str, ir: dict[str, Any]) -> None: ...

    @abstractmethod
    def load_packages(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Return (name, version, ir) for every persisted package."""

    # -- transition events ------------------------------------------------- #

    @abstractmethod
    def record_event(self, event: TransitionEvent) -> None: ...

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[TransitionEvent]: ...

    @abstractmethod
    def list_events(self) -> list[TransitionEvent]: ...

    @abstractmethod
    def update_event(self, event: TransitionEvent) -> None: ...

    # -- shared behaviour -------------------------------------------------- #

    def set_outcome(
        self, event_id: str, observed_state: dict[str, dict], outcome: str
    ) -> TransitionEvent:
        """Attach an observed outcome and compute prediction error (§15)."""
        event = self.get_event(event_id)
        if event is None:
            raise KeyError(event_id)
        event.observed_state_after = observed_state
        event.outcome = outcome
        event.prediction_error = prediction_error(event.predicted_state_after, observed_state)
        self.update_event(event)
        return event


class InMemoryStore(Store):
    def __init__(self) -> None:
        self._packages: dict[tuple[str, str], dict] = {}
        self._events: dict[str, TransitionEvent] = {}

    def save_package(self, name, version, ir) -> None:
        self._packages[(name, version)] = ir

    def load_packages(self):
        return [(n, v, ir) for (n, v), ir in self._packages.items()]

    def record_event(self, event) -> None:
        self._events[event.id] = event

    def get_event(self, event_id):
        return self._events.get(event_id)

    def list_events(self):
        return list(self._events.values())

    def update_event(self, event) -> None:
        self._events[event.id] = event
