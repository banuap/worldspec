"""End-to-end compiler pipeline (§9).

    WorldSpec YAML -> parser -> AST -> syntax validation -> semantic validation
    -> canonical IR

`validate_model` runs everything up to and including semantic validation.
`compile_model` additionally produces the IR (only when there are no errors).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from worldspec.compiler.ast import Model
from worldspec.compiler.ir import model_to_ir
from worldspec.compiler.parser import parse_model, parse_text
from worldspec.compiler.validator import validate_semantics
from worldspec.diagnostics import Diagnostic, DiagnosticBag


@dataclass
class CompileResult:
    model: Model
    diagnostics: list[Diagnostic]
    ir: Optional[dict[str, Any]] = None

    @property
    def ok(self) -> bool:
        return not any(d.severity.value == "error" for d in self.diagnostics)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity.value == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity.value == "warning"]


def _run_front_end(path_or_text, *, as_text: bool, model_name: Optional[str]):
    if as_text:
        model, bag = parse_text(path_or_text, model_name=model_name or "model")
    else:
        model, bag = parse_model(path_or_text, model_name=model_name)
    # Only attempt semantic validation if parsing produced no *structural*
    # errors that would make cross-referencing meaningless. We still run it on
    # warnings.
    if not bag.has_errors:
        validate_semantics(model, bag)
    return model, bag


def validate_model(
    path: str | Path, *, model_name: Optional[str] = None
) -> CompileResult:
    model, bag = _run_front_end(path, as_text=False, model_name=model_name)
    return CompileResult(model=model, diagnostics=bag.items)


def validate_text(text: str, *, model_name: str = "model") -> CompileResult:
    model, bag = _run_front_end(text, as_text=True, model_name=model_name)
    return CompileResult(model=model, diagnostics=bag.items)


def compile_model(
    path: str | Path, *, model_name: Optional[str] = None
) -> CompileResult:
    result = validate_model(path, model_name=model_name)
    if result.ok:
        result.ir = model_to_ir(result.model)
    return result


def compile_text(text: str, *, model_name: str = "model") -> CompileResult:
    result = validate_text(text, model_name=model_name)
    if result.ok:
        result.ir = model_to_ir(result.model)
    return result
