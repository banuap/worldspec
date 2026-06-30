"""Model-builder orchestrator: survey -> generate -> validate (-> repair).

The compiler is the guardrail: whatever the heuristic or LLM produces is compiled
before it is returned, so a built model is always either valid or reported with
actionable diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from worldspec.builder import heuristic, llm
from worldspec.builder.survey import Survey, SurveyError, cleanup, survey_repo
from worldspec.compiler.pipeline import compile_text


@dataclass
class BuildResult:
    name: str
    method: str                      # "llm" | "heuristic"
    model_yaml: str
    ok: bool
    diagnostics: list[dict] = field(default_factory=list)
    context: Optional[dict] = None
    survey: Optional[dict] = None
    note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "ok": self.ok,
            "modelYaml": self.model_yaml,
            "diagnostics": self.diagnostics,
            "context": self.context,
            "survey": self.survey,
            "note": self.note,
        }


def _diags(result) -> list[dict]:
    return [d.model_dump() for d in result.diagnostics]


def _construct_count(result) -> int:
    return len(result.ir["constructs"]) if result.ir else 0


def _generate_and_validate(survey, name, **kw):
    """One LLM generation + up to one compiler-driven repair round."""
    yaml_text = llm.build_with_llm(survey, name, **kw)
    result = compile_text(yaml_text, model_name=name)
    if not result.ok:
        errors = "\n".join(d.render() for d in result.errors)
        yaml_text = llm.build_with_llm(survey, name, errors=errors, prior=yaml_text)
        result = compile_text(yaml_text, model_name=name)
    return yaml_text, result


def build_model(source: str, name: str, *, prefer_llm: bool = True, rich: bool = True) -> BuildResult:
    survey, tmp = survey_repo(source)
    try:
        use_llm = prefer_llm and llm.is_available()
        note = None

        if use_llm:
            yaml_text, result = _generate_and_validate(survey, name)
            # Enrichment pass: expand a valid-but-thin model into a comprehensive one,
            # keeping the richer version only if it still compiles and adds constructs.
            if rich and result.ok:
                e_yaml, e_result = _generate_and_validate(survey, name, enrich=yaml_text)
                if e_result.ok and _construct_count(e_result) >= _construct_count(result):
                    yaml_text, result = e_yaml, e_result
            return BuildResult(
                name=name, method="llm", model_yaml=yaml_text, ok=result.ok,
                diagnostics=_diags(result), context=None, survey=survey.summary(),
            )

        if prefer_llm and not llm.is_available():
            note = ("LLM extraction requested but no provider is configured "
                    "(set GEMINI_API_KEY or ANTHROPIC_API_KEY). Generated a heuristic "
                    "starter model instead.")
        yaml_text, context = heuristic.build_heuristic(survey, name)
        result = compile_text(yaml_text, model_name=name)
        return BuildResult(
            name=name, method="heuristic", model_yaml=yaml_text, ok=result.ok,
            diagnostics=_diags(result), context=context, survey=survey.summary(), note=note,
        )
    finally:
        cleanup(tmp)
