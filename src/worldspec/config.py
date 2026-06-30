"""Lightweight configuration + .env loading (no external dependency).

Secrets (API keys) are read from the environment / a gitignored ``.env`` file —
never hard-coded. ``load_env`` is called at CLI and API startup.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


USER_CONFIG = Path.home() / ".worldspec" / ".env"


def _parse_into_environ(p: Path) -> None:
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_env(path: str | Path = ".env") -> None:
    """Load ``KEY=VALUE`` config into os.environ (no override) from, in order:

    1. the given ``.env`` (CWD, or searched upward toward the repo root), then
    2. the user-level config ``~/.worldspec/.env`` (works from any directory).
    """
    if os.environ.get("WORLDSPEC_NO_DOTENV"):
        return  # tests disable .env loading for deterministic, offline runs

    sources: list[Path] = []
    p = Path(path)
    if p.is_absolute():
        if p.is_file():
            sources.append(p)
    else:
        for parent in [Path.cwd(), *Path.cwd().parents]:
            candidate = parent / path
            if candidate.is_file():
                sources.append(candidate)
                break
    if USER_CONFIG.is_file():
        sources.append(USER_CONFIG)

    for src in sources:
        _parse_into_environ(src)


def llm_provider() -> Optional[str]:
    """Resolve the active LLM provider from config, or None if unconfigured.

    Recognized providers: ``gemini``, ``anthropic``, and ``copilot`` (an
    OpenAI-compatible HTTP endpoint, e.g. a VS Code Copilot bridge; ``openai``
    is accepted as an alias). Explicit ``WORLDSPEC_LLM_PROVIDER`` wins; otherwise
    a provider is inferred from whichever credential/endpoint is present.
    """
    explicit = os.environ.get("WORLDSPEC_LLM_PROVIDER")
    if explicit:
        prov = explicit.lower()
        return "copilot" if prov == "openai" else prov
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("WORLDSPEC_LLM_BASE_URL"):
        return "copilot"
    return None


def llm_model() -> str:
    if os.environ.get("WORLDSPEC_LLM_MODEL"):
        return os.environ["WORLDSPEC_LLM_MODEL"]
    provider = llm_provider()
    if provider == "gemini":
        return "gemini-2.5-flash"
    if provider == "copilot":
        return "gpt-4o"
    return "claude-sonnet-4-6"


def gemini_api_key() -> Optional[str]:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def llm_base_url() -> str:
    """Base URL for an OpenAI-compatible endpoint (the ``copilot`` provider).

    Defaults to a local VS Code Copilot bridge on ``http://localhost:4141/v1``.
    Point ``WORLDSPEC_LLM_BASE_URL`` at any OpenAI-compatible gateway.
    """
    return os.environ.get("WORLDSPEC_LLM_BASE_URL", "http://localhost:4141/v1")


def llm_api_key() -> Optional[str]:
    """Bearer token for the OpenAI-compatible endpoint, if the bridge needs one.

    Many local Copilot bridges accept any value (or none); some require a token.
    """
    return os.environ.get("WORLDSPEC_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
