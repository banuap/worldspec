"""Model-builder tests (offline: local fixture repo, heuristic path)."""

import json

import pytest
from fastapi.testclient import TestClient

from worldspec.api import create_app
from worldspec.builder import build_model, survey_repo
from worldspec.builder.survey import SurveyError
from worldspec.compiler.ir import model_to_ir
from worldspec.compiler.pipeline import validate_text
from worldspec.runtime import RuntimeModel, build_world


@pytest.fixture
def java_repo(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "Main.java").write_text(
        "import javax.swing.*;\npublic class Main { void go(){ new Helper(); } }\n", encoding="utf-8"
    )
    (src / "Helper.java").write_text("public class Helper { }\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "MainTest.java").write_text("class MainTest {}\n", encoding="utf-8")
    return tmp_path


def test_survey_detects_stack_and_units(java_repo):
    survey, tmp = survey_repo(str(java_repo))
    assert tmp is None  # local path: nothing to clean
    assert survey.stack == "java-swing"
    names = {u.name for u in survey.units}
    assert {"Main", "Helper"} <= names
    assert survey.has_tests is True


def test_survey_missing_path():
    with pytest.raises(SurveyError):
        survey_repo("/no/such/path/xyz")


def test_heuristic_build_is_valid_and_runnable(java_repo):
    result = build_model(str(java_repo), "fixture", prefer_llm=False)
    assert result.ok, result.diagnostics
    assert result.method == "heuristic"
    # the generated YAML compiles cleanly
    compiled = validate_text(result.model_yaml, model_name="fixture")
    assert compiled.ok
    # the generated context loads into a runtime world
    model = RuntimeModel.from_ir(model_to_ir(compiled.model))
    world = build_world(model, result.context)
    assert any(i.type == "Module" for i in world.entities.values())


def test_prefer_llm_without_key_falls_back(java_repo):
    result = build_model(str(java_repo), "fixture", prefer_llm=True)
    # no ANTHROPIC_API_KEY in the test env -> heuristic with an explanatory note
    assert result.method == "heuristic"
    assert result.note and "ANTHROPIC_API_KEY" in result.note


def test_api_build_registers_model(tmp_path, java_repo):
    import os

    os.environ["WORLDSPEC_MODELS"] = str(tmp_path / "models")
    client = TestClient(create_app(bootstrap=False))
    r = client.post("/models/build", json={"repo": str(java_repo), "name": "fx", "useLLM": False})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["registered"] is True
    assert "fx" in {m["name"] for m in client.get("/models").json()}
    # files were written
    assert (tmp_path / "models" / "fx" / "model.yaml").exists()
