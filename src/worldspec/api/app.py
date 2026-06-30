"""WorldSpec REST API + Studio host (Experience Layer, §12).

Routes are thin: they validate input, call :class:`WorldSpecService`, and map
``ServiceError`` to HTTP responses. The Studio (Milestone 4) is served as static
files at ``/studio``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from worldspec import COMPILER_VERSION
from worldspec.api.service import ServiceError, WorldSpecService

_STATIC_DIR = Path(__file__).parent / "static"


# --------------------------- request bodies -------------------------------- #


class RegisterRequest(BaseModel):
    path: str
    name: Optional[str] = None


class SimulateRequest(BaseModel):
    model: str
    transition: Optional[str] = None
    context: dict[str, Any]
    actor: Optional[str] = None


class InspectRequest(BaseModel):
    model: str
    context: dict[str, Any]


class ImpactRequest(BaseModel):
    model: str
    context: dict[str, Any]
    entityId: str


class OutcomeRequest(BaseModel):
    observedState: dict[str, Any]
    outcome: str


class BuildRequest(BaseModel):
    repo: str
    name: str
    useLLM: bool = True
    rich: bool = True


def create_app(
    service: Optional[WorldSpecService] = None,
    *,
    store=None,
    bootstrap: bool = True,
) -> FastAPI:
    from worldspec.config import load_env

    load_env()
    service = service or WorldSpecService(store=store)
    if bootstrap:
        import logging

        log = logging.getLogger("worldspec.api")
        root = Path(os.environ.get("WORLDSPEC_MODELS", Path.cwd() / "models"))
        registered = service.bootstrap(root)
        if registered:
            log.info("Bootstrapped %d model(s) from %s: %s", len(registered), root, ", ".join(registered))
        else:
            log.warning(
                "No models found under %s. Run `worldspec serve` from the repo root "
                "(the folder containing models/), pass --models <dir>, or POST /models/register.",
                root,
            )

    app = FastAPI(
        title="WorldSpec API",
        version=COMPILER_VERSION,
        description="Model the enterprise. Predict the transition. Preserve what matters.",
    )
    app.state.service = service

    @app.middleware("http")
    async def _no_cache_studio(request, call_next):
        # The Studio is a live dev surface; never let the browser cache its assets.
        response = await call_next(request)
        if request.url.path.startswith("/studio"):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    def _handle(fn):
        try:
            return fn()
        except ServiceError as exc:
            raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})

    # ---- health & models ------------------------------------------------- #

    @app.get("/health")
    def health():
        from worldspec.config import llm_model, llm_provider

        provider = llm_provider()
        return {
            "status": "ok",
            "version": COMPILER_VERSION,
            "models": len(service.list_models()),
            "llm": {"provider": provider, "model": llm_model() if provider else None},
        }

    @app.get("/models")
    def list_models():
        return service.list_models()

    @app.post("/models/register")
    def register_model(req: RegisterRequest):
        return _handle(lambda: service.register_path(req.path, req.name, persist=True))

    @app.post("/models/build")
    def build_model(req: BuildRequest):
        return _handle(lambda: service.build_from_repo(req.repo, req.name, use_llm=req.useLLM, rich=req.rich))

    @app.get("/models/{name}")
    def get_model(name: str):
        return _handle(lambda: service.get_model(name))

    @app.get("/models/{name}/graph")
    def model_graph(name: str):
        return _handle(lambda: service.model_graph(name))

    # ---- simulation & evidence ------------------------------------------- #

    @app.post("/transitions/simulate")
    def simulate(req: SimulateRequest):
        context = dict(req.context)
        if req.transition:
            context.setdefault("transition", req.transition)
        return _handle(lambda: service.simulate(req.model, context, actor=req.actor))

    @app.get("/evidence/{decision_id}")
    def evidence(decision_id: str):
        return _handle(lambda: service.get_evidence(decision_id))

    # ---- transition-event ledger (§15) ----------------------------------- #

    @app.get("/events")
    def list_events():
        return service.list_events()

    @app.get("/events/{event_id}")
    def get_event(event_id: str):
        return _handle(lambda: service.get_event(event_id))

    @app.post("/events/{event_id}/outcome")
    def record_outcome(event_id: str, req: OutcomeRequest):
        return _handle(lambda: service.record_outcome(event_id, req.observedState, req.outcome))

    # ---- world inspection ------------------------------------------------ #

    @app.post("/world/inspect")
    def inspect(req: InspectRequest):
        return _handle(lambda: service.inspect_world(req.model, req.context))

    @app.post("/relationships/impact")
    def impact(req: ImpactRequest):
        return _handle(lambda: service.impact(req.model, req.context, req.entityId))

    # ---- Studio ---------------------------------------------------------- #

    if _STATIC_DIR.is_dir():
        app.mount("/studio", StaticFiles(directory=str(_STATIC_DIR), html=True), name="studio")

    @app.get("/")
    def root():
        return RedirectResponse(url="/studio/")

    return app


def _default_app() -> FastAPI:
    """Module-level app for ``uvicorn worldspec.api.app:app``.

    Uses a durable SQLite store when ``WORLDSPEC_STORE`` is set, else in-memory.
    """
    store = None
    store_path = os.environ.get("WORLDSPEC_STORE")
    if store_path:
        from worldspec.runtime.sqlite_store import SqliteStore

        store = SqliteStore(store_path)
    return create_app(store=store)


app = _default_app()
