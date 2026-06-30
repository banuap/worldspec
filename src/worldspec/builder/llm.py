"""Optional LLM-backed model extraction (Gemini, Anthropic, or a Copilot bridge).

When a provider is configured, this turns a repo survey into a *repo-tailored*
WorldSpec ontology. The compiler validates the output (and feeds errors back for
one repair round), so a wrong guess fails loudly rather than producing an
invalid model. Providers:

- ``gemini``    — `GEMINI_API_KEY`/`GOOGLE_API_KEY` (stdlib HTTP, no SDK).
- ``anthropic`` — `ANTHROPIC_API_KEY` (`pip install anthropic`).
- ``copilot``   — any OpenAI-compatible HTTP endpoint, e.g. a **VS Code Copilot
  bridge** that exposes Copilot's models on a local `/v1/chat/completions`.
  Set `WORLDSPEC_LLM_PROVIDER=copilot` and `WORLDSPEC_LLM_BASE_URL`
  (default `http://localhost:4141/v1`); also stdlib HTTP, no SDK.

Note: using any of these sends sampled repository source to the configured LLM.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Optional

from worldspec import config
from worldspec.builder.survey import Survey

_SPEC = """\
You generate WorldSpec v0.1 models in YAML. Each top-level key is "<construct> <Name>".
Constructs: entity, relationship, state, invariant, action, transition.
Names are UpperCamelCase EXCEPT relationships which are lowerCamelCase.
- entity: { description?, identity: [propName...], properties: { name: {type, required?, values?(enum), target?(ref)} } }
  types: string|int|float|bool|datetime|enum|ref. enum needs values:[...]; ref needs target:<Entity>.
- relationship: { from: <Entity>, to: <Entity>, cardinality: one|many, temporal?: bool }
- state: { entity: <Entity>, dimensions: { name: {type,...} } }
- invariant: { appliesTo: <Entity>, expression, severity: info|warning|high|critical, onViolation: {action: block_transition|warn|record} }
  expression comparison: {operator: "=="|"!="|"<"|"<="|">"|">=", left: <operand>, right: <operand>}
  expression logical: {operator: and|or|not, operands: [expression...]}
  operand: a literal scalar, or {path: "field"}, or {function: count|sum|min|max|exists, path: "field"}
  Every path must be a declared property/dimension of the appliesTo entity.
- action: { inputs: { name: {type: ref, target: <Entity>} }, preconditions?: ["path == value"...], effects: ["path = value"...], rollback?: [...] }
  A precondition/effect path's first segment must be a declared input name.
- transition: { action: <Action>, from?: {...}, to?: {...}, preserves?: [<Invariant>...] }
Output ONLY valid YAML for the model. No prose, no markdown code fences.
"""


def is_available() -> bool:
    provider = config.llm_provider()
    if provider == "gemini":
        return bool(config.gemini_api_key())
    if provider == "anthropic":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        import os
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if provider == "copilot":
        # An OpenAI-compatible bridge (e.g. VS Code Copilot) reachable over HTTP.
        return bool(config.llm_base_url())
    return False


def _survey_brief(survey: Survey) -> str:
    lines = [
        f"Repository stack: {survey.stack}",
        f"Languages: {survey.languages}",
        f"Detected concerns: {sorted(k for k, v in survey.signals.items() if v) or 'none'}",
        f"External systems: {survey.externals or 'none'}",
        f"Has tests: {survey.has_tests}",
        f"Source units ({len(survey.units)}): {', '.join(u.name for u in survey.units[:80])}",
        f"\nFile inventory ({len(survey.files)} shown):\n  " + "\n  ".join(survey.files[:200]),
        "\nSource samples:",
    ]
    for path, text in list(survey.samples.items())[:20]:
        lines.append(f"\n=== {path} ===\n{text[:8000]}")
    return "\n".join(lines)


_BREADTH = """\
Build a COMPREHENSIVE model — capture the real domain, not a toy subset.
- Entities: model every significant domain concept you can infer (typically 6-15),
  each with meaningful properties (use enum for fixed value sets, ref for links).
- Relationships: capture how entities connect (owns, references, reads, writes,
  produces, consumes, dependsOn, ...). lowerCamelCase names.
- States: for entities that change, define a state with several dimensions
  (status enums, counts, flags, authority refs).
- Invariants: THE MOST IMPORTANT PART. Write MULTIPLE (aim for 6+) across these
  categories where they apply: data integrity (non-negative amounts, totals
  reconcile), referential consistency (single source of truth, no orphans),
  security (no plaintext secrets, authorization coverage), lifecycle/state-machine
  validity, and SLA/freshness (sync recency, batch completion). Use count/sum
  aggregates and and/or/not where useful. Every path must be a declared
  property/dimension of the appliesTo entity.
- Actions: several, each with realistic preconditions, effects, AND a rollback.
- Transitions: 2-4 meaningful ones (a modernization/cutover, a sync, a lifecycle
  change), each preserving the relevant invariants.
"""


def _prompt(survey: Survey, model_name: str, errors: Optional[str], prior: Optional[str], enrich: Optional[str]) -> str:
    if errors and prior:
        return (
            f"The following WorldSpec model failed validation:\n\n{prior}\n\n"
            f"Compiler errors:\n{errors}\n\nReturn a corrected, valid model. YAML only."
        )
    if enrich:
        return (
            "The WorldSpec model below is too thin. EXPAND it into a comprehensive model: "
            "add missing entities, relationships, and states; add MANY MORE invariants across "
            "data-integrity, referential-consistency, security, lifecycle, and SLA categories; "
            "ensure every action has a rollback; add 2-4 transitions. Keep everything valid "
            "(paths must reference declared fields of the appliesTo entity). Return the COMPLETE "
            f"expanded model as YAML only.\n\nCurrent model:\n{enrich}\n\n"
            f"System summary:\n{_survey_brief(survey)}"
        )
    return f"Build a WorldSpec model named '{model_name}'.\n\n{_BREADTH}\n\nSystem summary:\n{_survey_brief(survey)}"


def _extract_yaml(text: str) -> str:
    fence = re.search(r"```(?:yaml)?\s*(.*?)```", text, re.S)
    return (fence.group(1) if fence else text).strip()


class LLMError(Exception):
    code = "WS-BLD-0002"


def build_with_llm(
    survey: Survey, model_name: str, *, errors: Optional[str] = None,
    prior: Optional[str] = None, enrich: Optional[str] = None,
) -> str:
    provider = config.llm_provider()
    prompt = _prompt(survey, model_name, errors, prior, enrich)
    if provider == "gemini":
        return _extract_yaml(_gemini_generate(_SPEC, prompt, config.llm_model()))
    if provider == "anthropic":
        return _extract_yaml(_anthropic_generate(_SPEC, prompt, config.llm_model()))
    if provider == "copilot":
        return _extract_yaml(_openai_generate(_SPEC, prompt, config.llm_model()))
    raise LLMError("no LLM provider configured")


# --------------------------- Gemini (stdlib HTTP) ------------------------- #


def _gemini_generate(system: str, user: str, model: str) -> str:
    key = config.gemini_api_key()
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {
        "contents": [{"parts": [{"text": f"{system}\n\n{user}"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:300]
        raise LLMError(f"Gemini API error {exc.code} for model '{model}': {detail}")
    except urllib.error.URLError as exc:
        raise LLMError(f"Gemini API unreachable: {exc.reason}")
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError):
        raise LLMError(f"Unexpected Gemini response: {json.dumps(data)[:300]}")


# ----------------- OpenAI-compatible / Copilot bridge (HTTP) -------------- #


def _openai_generate(system: str, user: str, model: str) -> str:
    """Call an OpenAI-compatible `/chat/completions` endpoint (e.g. a VS Code
    Copilot bridge). No SDK dependency; auth via Bearer token when configured."""
    base = config.llm_base_url().rstrip("/")
    url = f"{base}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json"}
    key = config.llm_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")[:300]
        raise LLMError(f"Copilot/OpenAI endpoint error {exc.code} for model '{model}': {detail}")
    except urllib.error.URLError as exc:
        raise LLMError(
            f"Copilot/OpenAI endpoint unreachable at {url}: {exc.reason}. "
            "Is the VS Code Copilot bridge running? Set WORLDSPEC_LLM_BASE_URL."
        )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(f"Unexpected Copilot/OpenAI response: {json.dumps(data)[:300]}")


# --------------------------- Anthropic (SDK) ------------------------------ #


def _anthropic_generate(system: str, user: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=4096, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
