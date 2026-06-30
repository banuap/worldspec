"""WorldSpec command-line interface (§10).

Output is CI-friendly: human-readable by default, ``--json`` for machines, and a
non-zero exit code whenever there are error diagnostics.

Commands implemented:
    worldspec init <dir>
    worldspec validate <file-or-dir>
    worldspec compile <file-or-dir> [--output PKG] [--emit ir|package]
    worldspec inspect <package.wspkg>
    worldspec simulate <transition> --model <pkg|dir> --context <json>   (Milestone 2)

`deploy` registers into a persistent runtime, which is not part of this build,
so it remains an honest stub.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from worldspec import COMPILER_VERSION
from worldspec.compiler.generators import build_package, read_package
from worldspec.compiler.pipeline import compile_model, validate_model
from worldspec.diagnostics import Diagnostic

app = typer.Typer(
    add_completion=False,
    help="WorldSpec - model the enterprise, predict the transition, preserve "
    "what matters.",
    no_args_is_help=True,
)

_err = typer.style("[x]", fg=typer.colors.RED, bold=True)
_ok = typer.style("[ok]", fg=typer.colors.GREEN, bold=True)
_warn = typer.style("[!]", fg=typer.colors.YELLOW, bold=True)


def _print_diagnostics(diags: list[Diagnostic]) -> None:
    for d in diags:
        marker = _err if d.severity.value == "error" else _warn
        typer.echo(f"\n{marker} {d.render()}")


def _summary(n_err: int, n_warn: int) -> str:
    return f"{n_err} error(s), {n_warn} warning(s)"


@app.command()
def version() -> None:
    """Print the compiler version."""
    typer.echo(f"worldspec {COMPILER_VERSION}")


@app.command()
def init(
    directory: Path = typer.Argument(Path("."), help="Target directory."),
) -> None:
    """Scaffold a minimal WorldSpec model directory."""
    directory.mkdir(parents=True, exist_ok=True)
    sample = directory / "model.yaml"
    if sample.exists():
        typer.echo(f"{_warn} {sample} already exists; leaving it untouched.")
        raise typer.Exit(code=0)
    sample.write_text(_STARTER_MODEL, encoding="utf-8")
    typer.echo(f"{_ok} Created {sample}")
    typer.echo("Next: worldspec validate " + str(directory))


@app.command()
def validate(
    path: Path = typer.Argument(..., help="A .yaml file or a model directory."),
    as_json: bool = typer.Option(False, "--json", help="Emit diagnostics as JSON."),
) -> None:
    """Parse and validate a model. Exits non-zero if there are errors."""
    result = validate_model(path)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "ok": result.ok,
                    "diagnostics": [d.model_dump() for d in result.diagnostics],
                },
                indent=2,
            )
        )
    else:
        _print_diagnostics(result.diagnostics)
        n_err, n_warn = len(result.errors), len(result.warnings)
        if result.ok:
            typer.echo(
                f"\n{_ok} {path}: valid "
                f"({len(result.model.all_construct_names())} constructs, "
                f"{n_warn} warning(s))."
            )
        else:
            typer.echo(f"\n{_err} {path}: invalid - {_summary(n_err, n_warn)}.")
    raise typer.Exit(code=0 if result.ok else 1)


@app.command()
def compile(
    path: Path = typer.Argument(..., help="A .yaml file or a model directory."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write a .wspkg package to this path."
    ),
    emit: str = typer.Option(
        "package", "--emit", help="What to print to stdout: 'ir' or 'package'."
    ),
) -> None:
    """Compile a model to canonical IR and (optionally) a .wspkg package."""
    result = compile_model(path)
    _print_diagnostics(result.diagnostics)
    if not result.ok:
        typer.echo(
            f"\n{_err} {path}: compilation failed - "
            f"{_summary(len(result.errors), len(result.warnings))}."
        )
        raise typer.Exit(code=1)

    assert result.ir is not None
    if output is not None:
        pkg = build_package(result.model, result.ir, output)
        typer.echo(f"\n{_ok} Wrote package {pkg}")
    if emit == "ir":
        typer.echo(json.dumps(result.ir, indent=2))
    elif output is None:
        # Nothing written and not asked for IR: still confirm success.
        typer.echo(
            f"\n{_ok} {path}: compiled "
            f"({len(result.ir['constructs'])} constructs). "
            "Pass --output to write a .wspkg."
        )
    raise typer.Exit(code=0)


@app.command()
def inspect(
    package: Path = typer.Argument(..., help="A .wspkg package."),
) -> None:
    """Show the manifest and contents of a compiled package."""
    if not package.exists():
        typer.echo(f"{_err} Package not found: {package}")
        raise typer.Exit(code=1)
    data = read_package(package)
    manifest = data["manifest"]
    typer.echo(f"{_ok} {manifest['name']}  (package {manifest['packageFormatVersion']})")
    typer.echo(f"  language {manifest['languageVersion']}  compiler {manifest['compilerVersion']}")
    typer.echo("  constructs:")
    for kind, n in manifest["constructCounts"].items():
        typer.echo(f"    {kind:<13} {n}")
    typer.echo(f"  entity schemas: {', '.join(data['schemas']) or '(none)'}")


@app.command()
def build(
    repo: str = typer.Argument(..., help="A GitHub URL (or local path) to model."),
    name: str = typer.Option(..., "--name", "-n", help="Name for the generated model."),
    out: Path = typer.Option(Path("models"), "--out", help="Models directory to write into."),
    use_llm: bool = typer.Option(True, "--llm/--no-llm", help="Use the LLM extractor if available."),
    rich: bool = typer.Option(True, "--rich/--lean", help="Run an enrichment pass for a fuller model (LLM only)."),
) -> None:
    """Build a WorldSpec model from a repository (heuristic, or LLM if configured)."""
    from worldspec.builder import build_model
    from worldspec.builder.survey import SurveyError
    from worldspec.config import load_env

    load_env()

    try:
        result = build_model(repo, name, prefer_llm=use_llm, rich=rich)
    except SurveyError as exc:
        typer.echo(f"{_err} {getattr(exc, 'code', 'WS-BLD-0001')}: {exc}")
        raise typer.Exit(code=1)

    typer.echo(f"\n{_ok if result.ok else _err} Built '{name}' via {result.method} "
               f"(stack: {result.survey['stack']}, {result.survey['unitCount']} units)")
    if result.note:
        typer.echo(f"  {_warn} {result.note}")
    _print_diagnostics_from_dicts(result.diagnostics)
    if not result.ok:
        typer.echo(f"\n{_err} Generated model did not validate; not written.")
        raise typer.Exit(code=1)

    target = out / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "model.yaml").write_text(result.model_yaml, encoding="utf-8")
    if result.context is not None:
        (target / "context.json").write_text(json.dumps(result.context, indent=2), encoding="utf-8")
    typer.echo(f"\n{_ok} Wrote {target}/model.yaml"
               + (f" + context.json" if result.context is not None else ""))
    typer.echo(f"     Next: worldspec validate {target}  |  worldspec serve")


def _print_diagnostics_from_dicts(diags: list[dict]) -> None:
    for d in diags:
        marker = _err if d.get("severity") == "error" else _warn
        loc = f" ({d.get('file')}:{d.get('line')})" if d.get("file") else ""
        typer.echo(f"  {marker} {d['code']}: {d['message']}{loc}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    models_dir: Optional[Path] = typer.Option(None, "--models", help="Directory of model dirs to auto-register."),
    store: Path = typer.Option(Path(".worldspec/worldspec.db"), "--store", help="Durable SQLite store path."),
) -> None:
    """Launch the WorldSpec REST API + Studio (http://host:port/studio/)."""
    import os

    import uvicorn

    from worldspec.config import llm_model, llm_provider, load_env

    if models_dir is not None:
        os.environ["WORLDSPEC_MODELS"] = str(models_dir)
    os.environ.setdefault("WORLDSPEC_STORE", str(store))
    load_env()  # ensure the API process (same process) sees provider keys
    prov = llm_provider()
    typer.echo(f"{_ok} WorldSpec Studio -> http://{host}:{port}/studio/")
    typer.echo(f"     API docs        -> http://{host}:{port}/docs")
    if prov:
        typer.echo(f"     LLM provider    -> {prov} ({llm_model()})")
    else:
        typer.echo(f"     {_warn} No LLM provider configured — 'Create Model' will use the "
                   "heuristic. Add a key to .env (GEMINI_API_KEY / ANTHROPIC_API_KEY) or "
                   "set WORLDSPEC_LLM_PROVIDER=copilot for a VS Code Copilot bridge.")
    uvicorn.run("worldspec.api.app:app", host=host, port=port, log_level="info")


@app.command()
def demo(
    model: Path = typer.Option(
        Path("models/application-modernization"), "--model", "-m",
        help="Model package or directory.",
    ),
    context: Path = typer.Option(
        Path("examples/investone-like-demo/context.json"), "--context", "-c",
    ),
) -> None:
    """Run the end-to-end demo (Milestone 3): estate -> state -> simulate."""
    from worldspec.api.service import ServiceError, WorldSpecService

    svc = WorldSpecService()
    try:
        summary = svc.register_path(str(model))
        ctx = json.loads(context.read_text(encoding="utf-8"))
    except ServiceError as exc:
        typer.echo(f"{_err} {exc.code}: {exc.message}")
        typer.echo("     Tip: run `worldspec demo` from the repo root "
                   "(the folder containing models/ and examples/).")
        raise typer.Exit(code=1)
    except OSError as exc:
        typer.echo(f"{_err} cannot read context file: {exc}")
        raise typer.Exit(code=1)
    name = summary["name"]

    typer.echo(f"\n{_ok} Model '{name}' "
               f"({summary['counts']['entity']} entities, {summary['counts']['invariant']} invariants)")

    graph = svc.model_graph(name)
    typer.echo(f"\n  Dependency graph: {len(graph['nodes'])} entities, {len(graph['edges'])} relationships")

    typer.echo("\n  Current-state invariant checks:")
    inspection = svc.inspect_world(name, ctx)
    for ent in inspection["entities"]:
        for chk in ent["invariants"]:
            mark = _ok if chk["passed"] else _err
            typer.echo(f"    {mark} {ent['id']}: {chk['invariant']} "
                       f"({'holds' if chk['passed'] else 'VIOLATED'})")

    typer.echo("\n  Simulating proposed transition...")
    result = svc.simulate(name, ctx, actor="demo")
    _render_simulation_dict(result)
    raise typer.Exit(code=0 if result["allowed"] else 3)


def _render_simulation_dict(result: dict) -> None:
    verdict = _ok if result["allowed"] else _err
    headline = "ALLOWED" if result["allowed"] else "BLOCKED"
    typer.echo(f"\n{verdict} {result['transition']} -> {headline}  (risk: {result['riskLevel']})")
    for v in result["violations"]:
        typer.echo(f"    {_err} [{v['severity']}] {v['reason']}")
    if result["recommendedTrajectory"]:
        typer.echo("\n  Recommended safer trajectory:")
        typer.echo("    " + " -> ".join(result["recommendedTrajectory"]))
    ev = result["evidence"]
    typer.echo(f"\n  Evidence {ev['decisionId']} (confidence {ev['confidence']})")


@app.command()
def deploy(
    package: Path = typer.Argument(..., help="A .wspkg package (or model directory)."),
    store: Path = typer.Option(Path(".worldspec/worldspec.db"), "--store", help="SQLite store path."),
) -> None:
    """Register a compiled package into a durable WorldSpec store."""
    from worldspec.api.service import WorldSpecService
    from worldspec.runtime.sqlite_store import SqliteStore

    svc = WorldSpecService(store=SqliteStore(store))
    try:
        summary = svc.register_path(str(package), persist=True)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"{_err} deploy failed: {exc}")
        raise typer.Exit(code=1)
    typer.echo(f"{_ok} Registered '{summary['name']}' into {store}")
    typer.echo(f"     constructs: {summary['counts']}")


@app.command()
def events(
    store: Path = typer.Option(Path(".worldspec/worldspec.db"), "--store", help="SQLite store path."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """List recorded transition events (the ML-prerequisite ledger, §15)."""
    from worldspec.runtime.sqlite_store import SqliteStore

    rows = [e.to_dict() for e in SqliteStore(store).list_events()]
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        raise typer.Exit(code=0)
    if not rows:
        typer.echo(f"{_warn} No events recorded in {store}.")
        raise typer.Exit(code=0)
    for e in rows:
        err = e["predictionError"]
        err_s = f", error_rate={err['errorRate']}" if err else ""
        typer.echo(
            f"  {e['id']}  {e['transition']} -> "
            f"{'allowed' if e['allowedPrediction'] else 'blocked'} "
            f"(risk {e['riskLevel']}, outcome {e['outcome']}{err_s})"
        )


@app.command()
def simulate(
    transition: str = typer.Argument(..., help="Transition name (overridden by context if present)."),
    model: Path = typer.Option(..., "--model", "-m", help="A .wspkg package or a model directory."),
    context: Path = typer.Option(..., "--context", "-c", help="A context JSON describing the world."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full result as JSON."),
    actor: Optional[str] = typer.Option(None, "--actor", help="Who is requesting the simulation."),
) -> None:
    """Simulate a transition against a runtime world and return evidence."""
    from datetime import datetime, timezone

    from worldspec.runtime import load_model, simulate_from_context
    from worldspec.runtime.errors import RuntimeError_

    try:
        rt_model = load_model(model)
        ctx = json.loads(context.read_text(encoding="utf-8"))
        ctx.setdefault("transition", transition)
        result = simulate_from_context(
            rt_model,
            ctx,
            actor=actor,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except (RuntimeError_, json.JSONDecodeError, OSError) as exc:
        code = getattr(exc, "code", "WS-RUN-0000")
        typer.echo(f"{_err} {code}: {exc}")
        raise typer.Exit(code=1)

    if as_json:
        typer.echo(json.dumps(result.to_dict(), indent=2))
        raise typer.Exit(code=0 if result.allowed else 3)

    _render_simulation(result)
    raise typer.Exit(code=0 if result.allowed else 3)


def _render_simulation(result) -> None:
    verdict = _ok if result.allowed else _err
    headline = "ALLOWED" if result.allowed else "BLOCKED"
    typer.echo(f"\n{verdict} {result.transition} -> {headline}  (risk: {result.risk_level})")
    typer.echo(f"  action: {result.action}")

    if result.violations:
        typer.echo("\n  Invariant violations:")
        for v in result.violations:
            typer.echo(f"    {_err} [{v.severity}] {v.explanation}")
    if result.passed:
        typer.echo("\n  Invariants preserved: " + ", ".join(sorted({p.invariant for p in result.passed})))

    typer.echo("\n  Impacted entities: " + (", ".join(result.impacted_entities) or "(none)"))

    typer.echo("\n  Risk breakdown:")
    for k, val in result.risk_components.items():
        typer.echo(f"    {k}: {val}")

    if result.recommended_trajectory:
        typer.echo("\n  Recommended trajectory:")
        typer.echo("    " + " -> ".join(result.recommended_trajectory))

    ev = result.evidence
    typer.echo(f"\n  Evidence {ev.decision_id} (confidence {ev.confidence}):")
    for a in ev.assumptions:
        typer.echo(f"    - {a}")


_STARTER_MODEL = """\
entity Application:
  description: A deployable enterprise software system
  identity: [applicationId]
  properties:
    applicationId: { type: string, required: true }
    name: { type: string, required: true }
    criticality: { type: enum, values: [low, medium, high, systemic] }
"""


if __name__ == "__main__":  # pragma: no cover
    app()
