"""Stable, machine- and human-readable diagnostics for the WorldSpec compiler.

Every problem the compiler reports is a :class:`Diagnostic` carrying a stable
error code (``WS-SYN-####`` for syntax/structure, ``WS-SEM-####`` for semantics),
a human message, the originating file, a best-effort line number, and an optional
"did you mean" suggestion. Operating rule 7/8: reject silent failure, provide
stable error codes.
"""

from __future__ import annotations

import difflib
from enum import Enum
from typing import Iterable, Optional

from pydantic import BaseModel


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Diagnostic(BaseModel):
    """A single compiler finding."""

    code: str
    message: str
    severity: Severity = Severity.ERROR
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None

    def render(self) -> str:
        """Render in the CI-friendly multi-line format from the spec."""
        head = f"{self.severity.value.upper()} {self.code}"
        lines = [head, self.message]
        if self.file:
            loc = self.file if self.line is None else f"{self.file}"
            lines.append(f"File: {loc}")
        if self.line is not None:
            lines.append(f"Line: {self.line}")
        if self.suggestion:
            lines.append(f"Suggestion: {self.suggestion}")
        return "\n".join(lines)

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.render()


class DiagnosticBag:
    """Accumulates diagnostics during a compile pass."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def add(self, diagnostic: Diagnostic) -> None:
        self._items.append(diagnostic)

    def error(
        self,
        code: str,
        message: str,
        *,
        file: Optional[str] = None,
        line: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        self.add(
            Diagnostic(
                code=code,
                message=message,
                severity=Severity.ERROR,
                file=file,
                line=line,
                suggestion=suggestion,
            )
        )

    def warning(
        self,
        code: str,
        message: str,
        *,
        file: Optional[str] = None,
        line: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        self.add(
            Diagnostic(
                code=code,
                message=message,
                severity=Severity.WARNING,
                file=file,
                line=line,
                suggestion=suggestion,
            )
        )

    def extend(self, others: Iterable[Diagnostic]) -> None:
        self._items.extend(others)

    @property
    def items(self) -> list[Diagnostic]:
        return list(self._items)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self._items if d.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self._items if d.severity is Severity.WARNING]

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


def suggest(name: str, candidates: Iterable[str]) -> Optional[str]:
    """Return the closest candidate to ``name`` for a "did you mean" hint."""
    matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    if matches:
        return f"Did you mean '{matches[0]}'?"
    return None


class CompileError(Exception):
    """Raised when a stage cannot continue. Carries the offending diagnostics."""

    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(d.message for d in diagnostics) or "compile error")
