"""Safe evaluation of invariant-expression IR.

Walks the structured expression (comparison / logical / aggregate / path /
literal) produced by the compiler. **No ``eval``** — the only operations are the
closed set of comparators, boolean connectives, and aggregate functions
(ADR-005).

Aggregate convention (documented in docs/open-questions.md): when an aggregate
path resolves to a *list*, the aggregate is computed over its elements; when it
resolves to a *number*, it is treated as a pre-aggregated value (the count/sum is
already materialised, e.g. ``activeWriters: 2``).
"""

from __future__ import annotations

import operator
from typing import Any

_COMPARATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


class ExpressionError(Exception):
    code = "WS-RUN-0050"


def _resolve_path(path: str, state: dict[str, Any]) -> Any:
    value: Any = state
    for seg in path.split("."):
        if isinstance(value, dict):
            value = value.get(seg)
        else:
            return None
    return value


def _aggregate(fn: str, value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        items = list(value)
        if fn == "count":
            return len(items)
        if fn == "sum":
            return sum(items)
        if fn == "min":
            return min(items) if items else None
        if fn == "max":
            return max(items) if items else None
        if fn == "exists":
            return len(items) > 0
    # scalar / pre-aggregated
    if fn in ("count", "sum"):
        return value if isinstance(value, (int, float)) else (0 if value is None else 1)
    if fn in ("min", "max"):
        return value
    if fn == "exists":
        return value is not None
    raise ExpressionError(f"unknown aggregate function '{fn}'")


def _eval_operand(operand: Any, state: dict[str, Any]) -> Any:
    if isinstance(operand, dict):
        if "function" in operand:
            return _aggregate(operand["function"], _resolve_path(operand["path"], state))
        if "path" in operand:
            return _resolve_path(operand["path"], state)
        raise ExpressionError(f"malformed operand: {operand!r}")
    # bare scalar literal
    return operand


def evaluate(expr: dict[str, Any], state: dict[str, Any]) -> bool:
    """Evaluate an invariant expression against a single instance's state."""
    if "operands" in expr:  # logical
        op = expr["operator"]
        results = [evaluate(child, state) for child in expr["operands"]]
        if op == "and":
            return all(results)
        if op == "or":
            return any(results)
        if op == "not":
            return not results[0]
        raise ExpressionError(f"unknown logical operator '{op}'")

    # comparison
    op = expr["operator"]
    cmp = _COMPARATORS.get(op)
    if cmp is None:
        raise ExpressionError(f"unknown comparator '{op}'")
    left = _eval_operand(expr["left"], state)
    right = _eval_operand(expr["right"], state)
    if left is None and op not in ("==", "!="):
        # An ordering comparison against missing state cannot be satisfied;
        # treat as a violation rather than crashing.
        return False
    try:
        return bool(cmp(left, right))
    except TypeError:
        return False
