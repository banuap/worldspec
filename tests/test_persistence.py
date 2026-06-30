"""Persistence + transition-event ledger tests (the ML prerequisite, §15)."""

import json

import pytest
from conftest import MODELS_DIR
from fastapi.testclient import TestClient

from worldspec.api import create_app
from worldspec.api.service import WorldSpecService
from worldspec.runtime.events import Outcome, prediction_error
from worldspec.runtime.sqlite_store import SqliteStore
from worldspec.runtime.store import InMemoryStore

APPMOD = str(MODELS_DIR / "application-modernization")
CONTEXT = json.loads(
    (MODELS_DIR.parent / "examples" / "investone-like-demo" / "context.json").read_text(encoding="utf-8")
)


def test_prediction_error_computation():
    predicted = {"D": {"a": 1, "b": "x"}}
    observed = {"D": {"a": 1, "b": "y"}}
    err = prediction_error(predicted, observed)
    assert err["comparedFields"] == 2
    assert err["mismatchCount"] == 1
    assert err["errorRate"] == 0.5
    assert err["mismatches"][0]["field"] == "b"


def test_event_recorded_with_state_capture():
    svc = WorldSpecService(store=InMemoryStore())
    svc.register_path(APPMOD)
    res = svc.simulate("application-modernization", CONTEXT, timestamp="2026-01-01T00:00:00Z")
    assert "eventId" in res
    assert res["stateBefore"]["SETTLEMENT.VSAM"]["activeWriters"] == 2
    events = svc.list_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["outcome"] == "pending"
    assert ev["allowedPrediction"] is False


def test_outcome_capture_sets_prediction_error():
    svc = WorldSpecService(store=InMemoryStore())
    svc.register_path(APPMOD)
    res = svc.simulate("application-modernization", CONTEXT, timestamp="2026-01-01T00:00:00Z")
    observed = {"SETTLEMENT.VSAM": dict(res["predictedStateAfter"]["SETTLEMENT.VSAM"])}
    observed["SETTLEMENT.VSAM"]["activeWriters"] = 1  # the real cutover disabled COBOL
    ev = svc.record_outcome(res["eventId"], observed, Outcome.SUCCESS.value)
    assert ev["outcome"] == "success"
    assert ev["predictionError"]["mismatchCount"] >= 1
    assert any(m["field"] == "activeWriters" for m in ev["predictionError"]["mismatches"])


def test_invalid_outcome_rejected():
    svc = WorldSpecService(store=InMemoryStore())
    svc.register_path(APPMOD)
    res = svc.simulate("application-modernization", CONTEXT)
    from worldspec.api.service import ServiceError

    with pytest.raises(ServiceError):
        svc.record_outcome(res["eventId"], {}, "banana")


def test_sqlite_durability(tmp_path):
    db = tmp_path / "store.db"
    svc = WorldSpecService(store=SqliteStore(db))
    svc.register_path(APPMOD, persist=True)
    res = svc.simulate("application-modernization", CONTEXT, timestamp="2026-01-01T00:00:00Z")
    svc.record_outcome(res["eventId"], {"SETTLEMENT.VSAM": {"activeWriters": 1}}, "rolled_back")

    # New process / new store object over the same file.
    svc2 = WorldSpecService(store=SqliteStore(db))
    assert "application-modernization" in {m["name"] for m in svc2.list_models()}
    events = svc2.list_events()
    assert len(events) == 1 and events[0]["outcome"] == "rolled_back"
    assert events[0]["predictionError"]["mismatchCount"] >= 1


def test_api_events_and_outcome_endpoints(tmp_path):
    import os

    os.environ["WORLDSPEC_MODELS"] = str(MODELS_DIR)
    client = TestClient(create_app(store=SqliteStore(tmp_path / "api.db")))
    sim = client.post("/transitions/simulate", json={"model": "application-modernization", "context": CONTEXT}).json()
    eid = sim["eventId"]
    assert client.get("/events").json()[0]["id"] == eid
    out = client.post(
        f"/events/{eid}/outcome",
        json={"observedState": {"SETTLEMENT.VSAM": {"activeWriters": 1}}, "outcome": "success"},
    )
    assert out.status_code == 200
    assert out.json()["outcome"] == "success"
    assert client.get(f"/events/{eid}").json()["predictionError"]["mismatchCount"] >= 1
