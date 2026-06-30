"""REST API + Studio tests (Experience Layer, §12)."""

import json

import pytest
from conftest import MODELS_DIR
from fastapi.testclient import TestClient

from worldspec.api import create_app

CONTEXT = json.loads(
    (MODELS_DIR.parent / "examples" / "investone-like-demo" / "context.json").read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def client():
    # Bootstrap from the repo's models/ directory.
    import os

    os.environ["WORLDSPEC_MODELS"] = str(MODELS_DIR)
    return TestClient(create_app())


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["models"] >= 2


def test_list_and_get_model(client):
    names = {m["name"] for m in client.get("/models").json()}
    assert {"application-modernization", "swing-legacy-assessment"} <= names
    m = client.get("/models/application-modernization").json()
    assert any(i["name"] == "SingleWriter" for i in m["invariants"])


def test_model_graph(client):
    g = client.get("/models/application-modernization/graph").json()
    assert len(g["nodes"]) == 8
    assert any(e["type"] == "writes" for e in g["edges"])


def test_unknown_model_404(client):
    r = client.get("/models/ghost")
    assert r.status_code == 404
    assert r.json()["detail"]["code"]


def test_simulate_blocked_and_evidence_roundtrip(client):
    r = client.post("/transitions/simulate", json={"model": "application-modernization", "context": CONTEXT})
    assert r.status_code == 200
    data = r.json()
    assert data["allowed"] is False
    assert data["riskLevel"] == "critical"
    assert data["recommendedTrajectory"] == ["ShadowRun", "CompareOutputs", "TransferWriteAuthority"]
    decision_id = data["evidence"]["decisionId"]
    ev = client.get(f"/evidence/{decision_id}")
    assert ev.status_code == 200
    assert "SingleWriter" in ev.json()["invariantsFailed"]


def test_evidence_missing_404(client):
    assert client.get("/evidence/dec-doesnotexist").status_code == 404


def test_world_inspect(client):
    r = client.post("/world/inspect", json={"model": "application-modernization", "context": CONTEXT})
    assert r.status_code == 200
    entities = {e["id"]: e for e in r.json()["entities"]}
    ds = entities["SETTLEMENT.VSAM"]
    single_writer = next(c for c in ds["invariants"] if c["invariant"] == "SingleWriter")
    assert single_writer["passed"] is False


def test_impact_endpoint(client):
    r = client.post(
        "/relationships/impact",
        json={"model": "application-modernization", "context": CONTEXT, "entityId": "JOB.SETTLE.020"},
    )
    assert r.status_code == 200
    assert "SETTLEMENT.VSAM" in r.json()["impacted"]


def test_studio_served(client):
    assert client.get("/", follow_redirects=False).status_code == 307
    index = client.get("/studio/")
    assert index.status_code == 200 and "WorldSpec Studio" in index.text
    assert client.get("/studio/app.js").status_code == 200
