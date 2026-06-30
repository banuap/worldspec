"""IR generation, package build/inspect, and the sample-model acceptance check."""

import json

from conftest import MODELS_DIR

from worldspec.compiler.generators import (
    build_package,
    entity_json_schema,
    read_package,
)
from worldspec.compiler.pipeline import compile_model, compile_text

SAMPLE = MODELS_DIR / "application-modernization"
SWING = MODELS_DIR / "swing-legacy-assessment"


def test_sample_model_compiles_clean():
    """Milestone 1 acceptance: the demo model validates and compiles."""
    result = compile_model(SAMPLE)
    assert result.ok, [d.render() for d in result.errors]
    assert result.warnings == []  # the curated model is warning-free
    assert result.ir is not None
    kinds = {c["kind"] for c in result.ir["constructs"]}
    assert kinds == {
        "entity",
        "relationship",
        "state",
        "invariant",
        "action",
        "transition",
    }


def test_swing_assessment_model_compiles_clean():
    """The legacy-Swing assessment ontology validates and compiles warning-free."""
    result = compile_model(SWING)
    assert result.ok, [d.render() for d in result.errors]
    assert result.warnings == []
    names = {c["name"] for c in result.ir["constructs"]}
    # The headline risk invariants are present.
    assert {"NoBlockingIoOnEDT", "NoPlaintextCredentials", "NoBusinessLogicInView"} <= names


def test_ir_invariant_shape_matches_spec():
    result = compile_model(SAMPLE)
    inv = next(
        c
        for c in result.ir["constructs"]
        if c["kind"] == "invariant" and c["name"] == "SingleWriter"
    )
    assert inv["targetType"] == "Dataset"
    assert inv["expression"] == {
        "operator": "<=",
        "left": {"function": "count", "path": "activeWriters"},
        "right": 1,
    }
    assert inv["severity"] == "critical"


def test_ir_is_json_serializable():
    result = compile_model(SAMPLE)
    # Round-trips through JSON without custom encoders.
    assert json.loads(json.dumps(result.ir)) == result.ir


def test_no_ir_when_invalid():
    r = compile_text("entity bad:\n  identity: [x]\n  properties: { x: {type: string} }\n")
    assert not r.ok
    assert r.ir is None


def test_entity_json_schema_required_fields():
    result = compile_model(SAMPLE)
    app = result.model.entities["Application"]
    schema = entity_json_schema(app, result.model.name)
    assert schema["type"] == "object"
    assert "applicationId" in schema["required"]  # from identity
    assert schema["properties"]["criticality"]["enum"] == [
        "low",
        "medium",
        "high",
        "systemic",
    ]


def test_package_roundtrip(tmp_path):
    result = compile_model(SAMPLE)
    out = tmp_path / "demo.wspkg"
    build_package(result.model, result.ir, out)
    assert out.exists()
    data = read_package(out)
    assert data["manifest"]["name"] == "application-modernization"
    assert data["manifest"]["constructCounts"]["entity"] == 8
    assert "Dataset" in data["schemas"]
    assert data["ontology"]["irVersion"] == "0.1.0"
