"""The WorldSpec compiler: parser -> AST -> validation -> canonical IR ->
generated artifacts. Kept independent of the (future) runtime (ADR-003)."""

from worldspec.compiler.pipeline import CompileResult, compile_model, validate_model

__all__ = ["CompileResult", "compile_model", "validate_model"]
