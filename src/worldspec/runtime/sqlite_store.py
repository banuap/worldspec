"""SQLite-backed durable store (stdlib only, zero infrastructure).

Implements the :class:`Store` interface so packages and transition events survive
process restarts without requiring a database server (instructions: do not
require Kubernetes/infra for local development). A PostgreSQL/Neo4j store would
implement the same interface (ADR-004).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from worldspec.runtime.events import TransitionEvent
from worldspec.runtime.store import Store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    ir TEXT NOT NULL,
    PRIMARY KEY (name, version)
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    model TEXT, transition TEXT, action TEXT, decision_id TEXT,
    allowed_prediction INTEGER, risk_level TEXT,
    state_before TEXT, predicted_state_after TEXT, observed_state_after TEXT,
    outcome TEXT, prediction_error TEXT, actor TEXT, timestamp TEXT
);
"""


class SqliteStore(Store):
    def __init__(self, path: str | Path = ".worldspec/worldspec.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI/uvicorn dispatch handlers across a
        # threadpool; a process-wide lock serialises access.
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- packages ---------------------------------------------------------- #

    def save_package(self, name, version, ir) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO packages (name, version, ir) VALUES (?, ?, ?)",
                (name, version, json.dumps(ir)),
            )
            self._conn.commit()

    def load_packages(self):
        with self._lock:
            rows = self._conn.execute("SELECT name, version, ir FROM packages").fetchall()
        return [(r["name"], r["version"], json.loads(r["ir"])) for r in rows]

    # -- events ------------------------------------------------------------ #

    def record_event(self, event) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO events
                   (id, model, transition, action, decision_id, allowed_prediction,
                    risk_level, state_before, predicted_state_after, observed_state_after,
                    outcome, prediction_error, actor, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.id, event.model, event.transition, event.action, event.decision_id,
                    1 if event.allowed_prediction else 0, event.risk_level,
                    json.dumps(event.state_before), json.dumps(event.predicted_state_after),
                    json.dumps(event.observed_state_after) if event.observed_state_after is not None else None,
                    event.outcome,
                    json.dumps(event.prediction_error) if event.prediction_error is not None else None,
                    event.actor, event.timestamp,
                ),
            )
            self._conn.commit()

    update_event = record_event  # INSERT OR REPLACE handles both

    def get_event(self, event_id):
        with self._lock:
            row = self._conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return self._row_to_event(row) if row else None

    def list_events(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM events ORDER BY timestamp").fetchall()
        return [self._row_to_event(r) for r in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> TransitionEvent:
        def j(v):
            return json.loads(v) if v is not None else None

        return TransitionEvent(
            id=row["id"], model=row["model"], transition=row["transition"],
            action=row["action"], decision_id=row["decision_id"],
            allowed_prediction=bool(row["allowed_prediction"]), risk_level=row["risk_level"],
            state_before=j(row["state_before"]) or {},
            predicted_state_after=j(row["predicted_state_after"]) or {},
            observed_state_after=j(row["observed_state_after"]),
            outcome=row["outcome"], prediction_error=j(row["prediction_error"]),
            actor=row["actor"], timestamp=row["timestamp"],
        )
