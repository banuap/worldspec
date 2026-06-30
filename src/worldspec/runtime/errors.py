"""Runtime error codes and exceptions (WS-RUN-####).

Mirrors the compiler's stable-code philosophy: reject silent failure, give
actionable messages.
"""

from __future__ import annotations


class RuntimeError_(Exception):
    """Base class for runtime errors carrying a stable code."""

    code = "WS-RUN-0000"

    def __init__(self, message: str, *, code: str | None = None):
        if code:
            self.code = code
        super().__init__(message)
        self.message = message


class ModelNotFound(RuntimeError_):
    code = "WS-RUN-0001"


class UnknownConstruct(RuntimeError_):
    code = "WS-RUN-0002"


class EntityTypeError(RuntimeError_):
    code = "WS-RUN-0010"


class IdentityError(RuntimeError_):
    code = "WS-RUN-0011"


class RelationshipError(RuntimeError_):
    code = "WS-RUN-0020"


class BindingError(RuntimeError_):
    code = "WS-RUN-0030"


class SimulationError(RuntimeError_):
    code = "WS-RUN-0040"
