"""CLI behaviour: exit codes and CI-friendly output."""

import json

from typer.testing import CliRunner

from conftest import MODELS_DIR

from worldspec.cli import app

runner = CliRunner()
SAMPLE = str(MODELS_DIR / "application-modernization")


def test_validate_ok_exit_zero():
    result = runner.invoke(app, ["validate", SAMPLE])
    assert result.exit_code == 0
    assert "valid" in result.stdout


def test_validate_json_output():
    result = runner.invoke(app, ["validate", SAMPLE, "--json"])
    assert result.exit_code == 0
    assert '"ok": true' in result.stdout


def test_validate_invalid_exit_one(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("entity A:\n  identity: [id]\n  properties:\n    id: { type: nope }\n")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "WS-SYN-0040" in result.stdout


def test_compile_writes_package(tmp_path):
    out = tmp_path / "pkg.wspkg"
    result = runner.invoke(app, ["compile", SAMPLE, "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()


def test_compile_emit_ir():
    result = runner.invoke(app, ["compile", SAMPLE, "--emit", "ir"])
    assert result.exit_code == 0
    assert '"irVersion"' in result.stdout


def test_inspect_package(tmp_path):
    out = tmp_path / "pkg.wspkg"
    runner.invoke(app, ["compile", SAMPLE, "--output", str(out)])
    result = runner.invoke(app, ["inspect", str(out)])
    assert result.exit_code == 0
    assert "application-modernization" in result.stdout


def test_init_scaffolds(tmp_path):
    target = tmp_path / "newmodel"
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code == 0
    assert (target / "model.yaml").exists()
    # The scaffold validates.
    v = runner.invoke(app, ["validate", str(target)])
    assert v.exit_code == 0


def test_deploy_persists_package(tmp_path):
    db = tmp_path / "deploy.db"
    result = runner.invoke(app, ["deploy", SAMPLE, "--store", str(db)])
    assert result.exit_code == 0
    assert "Registered" in result.stdout
    assert db.exists()


def test_demo_missing_path_is_actionable(tmp_path):
    result = runner.invoke(app, ["demo", "--model", str(tmp_path / "nope")])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_simulate_blocked_exit_three():
    ctx = str(MODELS_DIR.parent / "examples" / "investone-like-demo" / "context.json")
    result = runner.invoke(
        app,
        ["simulate", "COBOLToJava", "--model", SAMPLE, "--context", ctx],
    )
    # Blocked transition -> exit code 3, with the dual-write violation surfaced.
    assert result.exit_code == 3
    assert "BLOCKED" in result.stdout
    assert "SingleWriter" in result.stdout
    assert "ShadowRun -> CompareOutputs -> TransferWriteAuthority" in result.stdout


def test_simulate_json_mode():
    ctx = str(MODELS_DIR.parent / "examples" / "investone-like-demo" / "context.json")
    result = runner.invoke(
        app,
        ["simulate", "COBOLToJava", "--model", SAMPLE, "--context", ctx, "--json"],
    )
    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["allowed"] is False
    assert payload["riskLevel"] == "critical"
