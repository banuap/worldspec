"""WorldSpec YAML -> typed AST parser (with structural syntax validation).

The parser is a *pure* function of its inputs (operating rule: prefer pure
functions for parsing). It never executes model content; invariant expressions
and action predicate/effect strings are parsed into a safe AST, never ``eval``'d
(ADR-005, security rules).

Line numbers are tracked best-effort via PyYAML's node tree so diagnostics can
point at a file and line.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

from worldspec.compiler.ast import (
    AGGREGATE_FUNCTIONS,
    ALL_TYPES,
    COMPARISON_OPERATORS,
    LOGICAL_OPERATORS,
    Action,
    Aggregate,
    Assignment,
    Comparison,
    Entity,
    Expr,
    Invariant,
    Literalcls,
    Logical,
    Model,
    Operand,
    PathOperand,
    PathRef,
    Predicate,
    Relationship,
    State,
    Transition,
    TypeDecl,
    ValueOperand,
)
from worldspec.diagnostics import DiagnosticBag

# --------------------------------------------------------------------------- #
# Line-tracking YAML loading
# --------------------------------------------------------------------------- #


class LineDict(dict):
    """A dict that remembers the source line of each key."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines: dict[Any, int] = {}


class LineList(list):
    """A list that remembers the source line of each element."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines: list[int] = []


_SCALAR_LOADER = yaml.SafeLoader("")


def _convert(node: yaml.Node) -> Any:
    if isinstance(node, yaml.MappingNode):
        d = LineDict()
        for key_node, value_node in node.value:
            key = _convert(key_node)
            d[key] = _convert(value_node)
            d.lines[key] = key_node.start_mark.line + 1
        return d
    if isinstance(node, yaml.SequenceNode):
        lst = LineList()
        for item in node.value:
            lst.append(_convert(item))
            lst.lines.append(item.start_mark.line + 1)
        return lst
    return _SCALAR_LOADER.construct_object(node)


# --------------------------------------------------------------------------- #
# Identifier rules
# --------------------------------------------------------------------------- #

_CONSTRUCT_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_MEMBER_NAME_RE = re.compile(r"^[a-z][A-Za-z0-9_]*$")
_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_KNOWN_CONSTRUCTS = {
    "entity",
    "relationship",
    "state",
    "invariant",
    "action",
    "transition",
}
_VALID_SEVERITIES = {"info", "warning", "high", "critical"}
_VALID_ON_VIOLATION = {"block_transition", "warn", "record"}
_VALID_CARDINALITY = {"one", "many"}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse_model(
    path: str | Path, *, model_name: Optional[str] = None
) -> tuple[Model, DiagnosticBag]:
    """Parse a file or a directory of ``.yaml``/``.yml`` files into a Model."""
    bag = DiagnosticBag()
    p = Path(path)
    if p.is_dir():
        files = sorted([*p.glob("*.yaml"), *p.glob("*.yml")])
        name = model_name or p.name
    elif p.is_file():
        files = [p]
        name = model_name or p.stem
    else:
        bag.error("WS-SYN-0000", f"Path not found: {p}")
        return Model(name=model_name or str(p)), bag

    model = Model(name=name)
    if not files:
        bag.warning("WS-SYN-0004", f"No .yaml/.yml files found under {p}")
    for f in files:
        _parse_file(f, model, bag)
    return model, bag


def parse_text(
    text: str, *, file: str = "<string>", model_name: str = "model"
) -> tuple[Model, DiagnosticBag]:
    """Parse a single YAML document from a string (used by tests)."""
    bag = DiagnosticBag()
    model = Model(name=model_name)
    _parse_document(text, file, model, bag)
    return model, bag


# --------------------------------------------------------------------------- #
# File / document parsing
# --------------------------------------------------------------------------- #


def _parse_file(path: Path, model: Model, bag: DiagnosticBag) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem dependent
        bag.error("WS-SYN-0001", f"Cannot read file: {exc}", file=str(path))
        return
    _parse_document(text, str(path), model, bag)


def _parse_document(text: str, file: str, model: Model, bag: DiagnosticBag) -> None:
    try:
        root = yaml.compose(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = (mark.line + 1) if mark else None
        bag.error(
            "WS-SYN-0001",
            f"Invalid YAML: {getattr(exc, 'problem', exc)}",
            file=file,
            line=line,
        )
        return

    if root is None:
        return
    if not isinstance(root, yaml.MappingNode):
        bag.error(
            "WS-SYN-0002",
            "Top-level of a WorldSpec file must be a mapping of "
            "'<construct> <Name>' keys.",
            file=file,
            line=root.start_mark.line + 1,
        )
        return

    # Detect duplicate top-level keys at the node level: YAML silently keeps
    # only the last value for a repeated mapping key, which would otherwise
    # hide a duplicate construct.
    seen_keys: set[str] = set()
    for key_node, _ in root.value:
        if isinstance(key_node, yaml.ScalarNode):
            k = key_node.value
            if k in seen_keys:
                bag.error(
                    "WS-SYN-0003",
                    f"Duplicate top-level key '{k}'.",
                    file=file,
                    line=key_node.start_mark.line + 1,
                )
            seen_keys.add(k)

    doc = _convert(root)
    for raw_key, body in doc.items():
        line = doc.lines.get(raw_key)
        _parse_construct(raw_key, body, file, line, model, bag)


def _parse_construct(
    raw_key: Any,
    body: Any,
    file: str,
    line: Optional[int],
    model: Model,
    bag: DiagnosticBag,
) -> None:
    if not isinstance(raw_key, str) or len(raw_key.split()) != 2:
        bag.error(
            "WS-SYN-0010",
            f"Malformed top-level key {raw_key!r}; expected "
            "'<construct> <Name>'.",
            file=file,
            line=line,
        )
        return

    keyword, name = raw_key.split()
    if keyword not in _KNOWN_CONSTRUCTS:
        bag.error(
            "WS-SYN-0011",
            f"Unknown construct '{keyword}'.",
            file=file,
            line=line,
            suggestion=_closest(keyword, _KNOWN_CONSTRUCTS),
        )
        return
    # Relationships are lowerCamelCase (dependsOn, reads, writes, ...);
    # all other constructs are UpperCamelCase.
    if keyword == "relationship":
        name_ok, expected = bool(_MEMBER_NAME_RE.match(name)), "lowerCamelCase"
    else:
        name_ok, expected = bool(_CONSTRUCT_NAME_RE.match(name)), "UpperCamelCase"
    if not name_ok:
        bag.error(
            "WS-SYN-0012",
            f"Invalid {keyword} name '{name}'; must be {expected}.",
            file=file,
            line=line,
        )
        return
    if name in model.all_construct_names():
        bag.error(
            "WS-SYN-0003",
            f"Duplicate construct name '{name}'.",
            file=file,
            line=line,
        )
        return
    if not isinstance(body, dict):
        bag.error(
            "WS-SYN-0020",
            f"Body of '{raw_key}' must be a mapping.",
            file=file,
            line=line,
        )
        return

    dispatch = {
        "entity": _parse_entity,
        "relationship": _parse_relationship,
        "state": _parse_state,
        "invariant": _parse_invariant,
        "action": _parse_action,
        "transition": _parse_transition,
    }
    dispatch[keyword](name, body, file, line, model, bag)


# --------------------------------------------------------------------------- #
# Type declarations
# --------------------------------------------------------------------------- #


def _parse_type_decl(
    owner: str,
    member: str,
    decl: Any,
    file: str,
    line: Optional[int],
    bag: DiagnosticBag,
) -> Optional[TypeDecl]:
    if not isinstance(decl, dict):
        bag.error(
            "WS-SYN-0040",
            f"Declaration of '{member}' in {owner} must be a mapping with a "
            "'type'.",
            file=file,
            line=line,
        )
        return None
    decl_line = decl.lines.get("type", line) if isinstance(decl, LineDict) else line
    type_name = decl.get("type")
    if type_name not in ALL_TYPES:
        bag.error(
            "WS-SYN-0040",
            f"Invalid type '{type_name}' for '{member}' in {owner}.",
            file=file,
            line=decl_line,
            suggestion=_closest(str(type_name), ALL_TYPES),
        )
        return None

    values = decl.get("values")
    target = decl.get("target")
    if type_name == "enum":
        if not isinstance(values, list) or not values:
            bag.error(
                "WS-SYN-0041",
                f"enum '{member}' in {owner} must declare a non-empty 'values' "
                "list.",
                file=file,
                line=decl_line,
            )
            return None
        if len(set(map(str, values))) != len(values):
            bag.error(
                "WS-SYN-0041",
                f"enum '{member}' in {owner} has duplicate values.",
                file=file,
                line=decl_line,
            )
            return None
    if type_name == "ref" and not isinstance(target, str):
        bag.error(
            "WS-SYN-0042",
            f"ref '{member}' in {owner} must declare a 'target' entity name.",
            file=file,
            line=decl_line,
        )
        return None

    return TypeDecl(
        type=type_name,
        required=bool(decl.get("required", False)),
        values=list(values) if isinstance(values, list) else None,
        target=target if isinstance(target, str) else None,
        line=decl_line,
    )


def _parse_members(
    owner: str,
    raw: Any,
    field: str,
    file: str,
    line: Optional[int],
    bag: DiagnosticBag,
) -> dict[str, TypeDecl]:
    out: dict[str, TypeDecl] = {}
    if not isinstance(raw, dict):
        bag.error(
            "WS-SYN-0031",
            f"'{field}' of {owner} must be a mapping.",
            file=file,
            line=line,
        )
        return out
    for member, decl in raw.items():
        member_line = raw.lines.get(member, line) if isinstance(raw, LineDict) else line
        if not _MEMBER_NAME_RE.match(str(member)):
            bag.error(
                "WS-SYN-0090",
                f"Invalid member name '{member}' in {owner}; must be "
                "lowerCamelCase.",
                file=file,
                line=member_line,
            )
            continue
        td = _parse_type_decl(owner, str(member), decl, file, member_line, bag)
        if td is not None:
            out[str(member)] = td
    return out


# --------------------------------------------------------------------------- #
# Construct parsers
# --------------------------------------------------------------------------- #


def _require(body, field, owner, file, line, bag, code="WS-SYN-0030") -> bool:
    if field not in body:
        bag.error(
            code,
            f"{owner} is missing required field '{field}'.",
            file=file,
            line=line,
        )
        return False
    return True


def _parse_entity(name, body, file, line, model, bag):
    owner = f"entity {name}"
    ok = _require(body, "properties", owner, file, line, bag)
    identity = body.get("identity", [])
    if not isinstance(identity, list) or not identity:
        bag.error(
            "WS-SYN-0030",
            f"{owner} must declare a non-empty 'identity' list.",
            file=file,
            line=line,
        )
        identity = identity if isinstance(identity, list) else []
    properties = (
        _parse_members(owner, body.get("properties"), "properties", file, line, bag)
        if ok
        else {}
    )
    model.entities[name] = Entity(
        name=name,
        description=body.get("description"),
        identity=[str(i) for i in identity],
        properties=properties,
        line=line,
    )


def _parse_relationship(name, body, file, line, model, bag):
    owner = f"relationship {name}"
    ok = all(
        _require(body, f, owner, file, line, bag) for f in ("from", "to", "cardinality")
    )
    cardinality = body.get("cardinality", "many")
    if cardinality not in _VALID_CARDINALITY:
        bag.error(
            "WS-SYN-0070",
            f"{owner} has invalid cardinality '{cardinality}'; expected one of "
            f"{sorted(_VALID_CARDINALITY)}.",
            file=file,
            line=line,
        )
    if not ok:
        return
    model.relationships[name] = Relationship(
        name=name,
        **{"from": str(body.get("from"))},
        to=str(body.get("to")),
        cardinality=str(cardinality),
        temporal=bool(body.get("temporal", False)),
        line=line,
    )


def _parse_state(name, body, file, line, model, bag):
    owner = f"state {name}"
    ok = _require(body, "entity", owner, file, line, bag) and _require(
        body, "dimensions", owner, file, line, bag
    )
    if not ok:
        return
    dimensions = _parse_members(
        owner, body.get("dimensions"), "dimensions", file, line, bag
    )
    model.states[name] = State(
        name=name,
        entity=str(body.get("entity")),
        dimensions=dimensions,
        line=line,
    )


def _parse_invariant(name, body, file, line, model, bag):
    owner = f"invariant {name}"
    ok = _require(body, "appliesTo", owner, file, line, bag) and _require(
        body, "expression", owner, file, line, bag
    )
    if not ok:
        return
    severity = body.get("severity", "warning")
    if severity not in _VALID_SEVERITIES:
        bag.error(
            "WS-SYN-0060",
            f"{owner} has invalid severity '{severity}'; expected one of "
            f"{sorted(_VALID_SEVERITIES)}.",
            file=file,
            line=line,
        )
        severity = "warning"
    on_violation = "warn"
    ov = body.get("onViolation")
    if isinstance(ov, dict) and "action" in ov:
        on_violation = ov.get("action")
        if on_violation not in _VALID_ON_VIOLATION:
            bag.error(
                "WS-SYN-0061",
                f"{owner} has invalid onViolation.action '{on_violation}'.",
                file=file,
                line=line,
            )
            on_violation = "warn"
    expr = _parse_expression(body.get("expression"), owner, file, line, bag)
    if expr is None:
        return
    model.invariants[name] = Invariant(
        name=name,
        appliesTo=str(body.get("appliesTo")),
        expression=expr,
        severity=str(severity),
        on_violation=str(on_violation),
        line=line,
    )


def _parse_action(name, body, file, line, model, bag):
    owner = f"action {name}"
    if not _require(body, "effects", owner, file, line, bag):
        return
    inputs = _parse_members(owner, body.get("inputs", {}), "inputs", file, line, bag)
    input_names = set(inputs)

    preconditions: list[Predicate] = []
    raw_pre = body.get("preconditions", [])
    if raw_pre and not isinstance(raw_pre, list):
        bag.error("WS-SYN-0031", f"'preconditions' of {owner} must be a list.", file=file, line=line)
        raw_pre = []
    for idx, item in enumerate(raw_pre or []):
        item_line = raw_pre.lines[idx] if isinstance(raw_pre, LineList) else line
        pred = _parse_predicate(str(item), owner, file, item_line, bag, input_names)
        if pred is not None:
            preconditions.append(pred)

    effects = _parse_assignments(
        body.get("effects"), owner, "effects", "WS-SYN-0081", file, line, bag, input_names
    )
    rollback = _parse_assignments(
        body.get("rollback", []), owner, "rollback", "WS-SYN-0081", file, line, bag, input_names
    )
    if not effects:
        bag.error(
            "WS-SYN-0030",
            f"{owner} must declare at least one effect.",
            file=file,
            line=line,
        )
        return
    model.actions[name] = Action(
        name=name,
        inputs=inputs,
        preconditions=preconditions,
        effects=effects,
        rollback=rollback,
        line=line,
    )


def _parse_assignments(raw, owner, field, code, file, line, bag, input_names=frozenset()) -> list[Assignment]:
    out: list[Assignment] = []
    if raw and not isinstance(raw, list):
        bag.error("WS-SYN-0031", f"'{field}' of {owner} must be a list.", file=file, line=line)
        return out
    for idx, item in enumerate(raw or []):
        item_line = raw.lines[idx] if isinstance(raw, LineList) else line
        asg = _parse_assignment(str(item), owner, file, item_line, bag, code=code, input_names=input_names)
        if asg is not None:
            out.append(asg)
    return out


def _parse_transition(name, body, file, line, model, bag):
    owner = f"transition {name}"
    if not _require(body, "action", owner, file, line, bag):
        return
    preserves = body.get("preserves", [])
    if preserves and not isinstance(preserves, list):
        bag.error("WS-SYN-0031", f"'preserves' of {owner} must be a list.", file=file, line=line)
        preserves = []
    model.transitions[name] = Transition(
        name=name,
        action=str(body.get("action")),
        **{"from": dict(body.get("from", {}) or {})},
        to=dict(body.get("to", {}) or {}),
        preserves=[str(p) for p in (preserves or [])],
        line=line,
    )


# --------------------------------------------------------------------------- #
# Invariant expression parsing (§4)
# --------------------------------------------------------------------------- #


def _parse_expression(
    node: Any, owner: str, file: str, line: Optional[int], bag: DiagnosticBag
) -> Optional[Expr]:
    if not isinstance(node, dict) or "operator" not in node:
        bag.error(
            "WS-SYN-0050",
            f"{owner} expression must be a mapping with an 'operator'.",
            file=file,
            line=line,
        )
        return None
    operator = node.get("operator")
    if operator in LOGICAL_OPERATORS:
        operands_raw = node.get("operands")
        if not isinstance(operands_raw, list) or not operands_raw:
            bag.error(
                "WS-SYN-0050",
                f"Logical operator '{operator}' in {owner} requires an "
                "'operands' list.",
                file=file,
                line=line,
            )
            return None
        if operator == "not" and len(operands_raw) != 1:
            bag.error(
                "WS-SYN-0051",
                f"'not' in {owner} takes exactly one operand.",
                file=file,
                line=line,
            )
            return None
        parsed = []
        for sub in operands_raw:
            child = _parse_expression(sub, owner, file, line, bag)
            if child is None:
                return None
            parsed.append(child)
        return Logical(operator=str(operator), operands=parsed)
    if operator in COMPARISON_OPERATORS:
        if "left" not in node or "right" not in node:
            bag.error(
                "WS-SYN-0050",
                f"Comparison in {owner} requires 'left' and 'right' operands.",
                file=file,
                line=line,
            )
            return None
        left = _parse_operand(node.get("left"), owner, file, line, bag)
        right = _parse_operand(node.get("right"), owner, file, line, bag)
        if left is None or right is None:
            return None
        return Comparison(operator=str(operator), left=left, right=right)

    bag.error(
        "WS-SYN-0051",
        f"Unknown operator '{operator}' in {owner}.",
        file=file,
        line=line,
        suggestion=_closest(str(operator), COMPARISON_OPERATORS | LOGICAL_OPERATORS),
    )
    return None


def _parse_operand(
    value: Any, owner: str, file: str, line: Optional[int], bag: DiagnosticBag
) -> Optional[Operand]:
    if isinstance(value, dict):
        if "function" in value:
            fn = value.get("function")
            if fn not in AGGREGATE_FUNCTIONS:
                bag.error(
                    "WS-SYN-0051",
                    f"Unknown aggregate function '{fn}' in {owner}.",
                    file=file,
                    line=line,
                    suggestion=_closest(str(fn), AGGREGATE_FUNCTIONS),
                )
                return None
            path = value.get("path")
            if not isinstance(path, str):
                bag.error(
                    "WS-SYN-0050",
                    f"Aggregate '{fn}' in {owner} requires a string 'path'.",
                    file=file,
                    line=line,
                )
                return None
            return Aggregate(function=str(fn), path=path)
        if "path" in value:
            path = value.get("path")
            if not isinstance(path, str):
                bag.error(
                    "WS-SYN-0050",
                    f"Operand 'path' in {owner} must be a string.",
                    file=file,
                    line=line,
                )
                return None
            return PathRef(path=path)
        bag.error(
            "WS-SYN-0050",
            f"Operand in {owner} must be a literal, a {{path}}, or a "
            "{{function,path}} aggregate.",
            file=file,
            line=line,
        )
        return None
    if isinstance(value, (str, int, float, bool)):
        return Literalcls(value=value)
    bag.error(
        "WS-SYN-0050",
        f"Unsupported operand {value!r} in {owner}.",
        file=file,
        line=line,
    )
    return None


# --------------------------------------------------------------------------- #
# Action mini-language parsing (§5) — safe, no eval
# --------------------------------------------------------------------------- #

_CMP_RE = re.compile(r"(==|!=|<=|>=|<|>)")
_ASSIGN_RE = re.compile(r"(?<![=<>!])=(?!=)")


def _parse_action_operand(
    token: str, owner: str, file: str, line: Optional[int], bag: DiagnosticBag,
    input_names=frozenset(),
) -> Optional[ValueOperand | PathOperand]:
    token = token.strip()
    # String literals may use double or single quotes.
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return ValueOperand(value=token[1:-1])
    if token == "true":
        return ValueOperand(value=True)
    if token == "false":
        return ValueOperand(value=False)
    try:
        return ValueOperand(value=int(token))
    except ValueError:
        pass
    try:
        return ValueOperand(value=float(token))
    except ValueError:
        pass
    if _PATH_RE.match(token):
        segments = token.split(".")
        # A multi-segment path, or a single token that names an action input, is
        # a path reference. A bare single token that is NOT an input is an
        # unquoted string literal (e.g. an enum value like Active/Draft).
        if len(segments) > 1 or segments[0] in input_names:
            return PathOperand(segments=segments)
        return ValueOperand(value=token)
    bag.error(
        "WS-SYN-0080",
        f"Cannot parse operand '{token}' in {owner}.",
        file=file,
        line=line,
    )
    return None


def _parse_predicate(
    text: str, owner: str, file: str, line: Optional[int], bag: DiagnosticBag,
    input_names=frozenset(),
) -> Optional[Predicate]:
    m = _CMP_RE.search(text)
    if not m:
        bag.error(
            "WS-SYN-0080",
            f"Precondition '{text}' in {owner} must be 'path <op> value'.",
            file=file,
            line=line,
        )
        return None
    left_s, right_s = text[: m.start()].strip(), text[m.end() :].strip()
    if not _PATH_RE.match(left_s):
        bag.error(
            "WS-SYN-0080",
            f"Left side of precondition '{text}' in {owner} must be a path.",
            file=file,
            line=line,
        )
        return None
    right = _parse_action_operand(right_s, owner, file, line, bag, input_names)
    if right is None:
        return None
    return Predicate(
        raw=text.strip(),
        left=PathOperand(segments=left_s.split(".")),
        operator=m.group(1),
        right=right,
        line=line,
    )


def _parse_assignment(
    text: str, owner: str, file: str, line: Optional[int], bag: DiagnosticBag, *, code: str,
    input_names=frozenset(),
) -> Optional[Assignment]:
    m = _ASSIGN_RE.search(text)
    if not m:
        bag.error(
            code,
            f"Effect '{text}' in {owner} must be 'path = value'.",
            file=file,
            line=line,
        )
        return None
    left_s, right_s = text[: m.start()].strip(), text[m.end() :].strip()
    if not _PATH_RE.match(left_s):
        bag.error(
            code,
            f"Left side of effect '{text}' in {owner} must be a path.",
            file=file,
            line=line,
        )
        return None
    right = _parse_action_operand(right_s, owner, file, line, bag, input_names)
    if right is None:
        return None
    return Assignment(
        raw=text.strip(),
        target=PathOperand(segments=left_s.split(".")),
        value=right,
        line=line,
    )


# --------------------------------------------------------------------------- #


def _closest(name: str, candidates) -> Optional[str]:
    from worldspec.diagnostics import suggest

    return suggest(name, candidates)
