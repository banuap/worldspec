"""Heuristic model builder — produce a *valid* starter model from a survey,
with no LLM required.

WorldSpec models describe *types*; a repo's actual files are *instances*. So the
heuristic emits a small, always-valid ontology (Module + dependencies + grounded
quality invariants) and a **context** mapping the discovered source units onto it
as instances. The richer, repo-tailored ontology is what the LLM path produces.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from worldspec.builder.survey import Survey

# Languages we will expose as the Module.language enum (always include the
# detected ones plus a fallback so the enum is never empty).
def _language_values(survey: Survey) -> list[str]:
    vals = sorted(survey.languages.keys()) or ["unknown"]
    if "unknown" not in vals:
        vals.append("unknown")
    return vals


def _ontology(survey: Survey) -> dict[str, Any]:
    return {
        "entity Module": {
            "description": "A source unit (class / program / module) in the codebase",
            "identity": ["moduleId"],
            "properties": {
                "moduleId": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
                "language": {"type": "enum", "values": _language_values(survey)},
            },
        },
        "entity System": {
            "description": "The codebase as a whole",
            "identity": ["systemId"],
            "properties": {
                "systemId": {"type": "string", "required": True},
                "name": {"type": "string", "required": True},
            },
        },
        "relationship dependsOn": {
            "from": "Module", "to": "Module", "cardinality": "many",
        },
        "relationship partOf": {
            "from": "Module", "to": "System", "cardinality": "one",
        },
        "state ModuleQuality": {
            "entity": "Module",
            "dimensions": {
                "lineCount": {"type": "int"},
                "hasTests": {"type": "bool"},
                "fanIn": {"type": "int"},
            },
        },
        "invariant BoundedModule": {
            "appliesTo": "Module",
            "expression": {"operator": "<=", "left": {"path": "lineCount"}, "right": 1500},
            "severity": "high",
            "onViolation": {"action": "warn"},
        },
        "invariant ModuleTested": {
            "appliesTo": "Module",
            "expression": {"operator": "==", "left": {"path": "hasTests"}, "right": True},
            "severity": "warning",
            "onViolation": {"action": "record"},
        },
        "invariant BoundedCoupling": {
            "appliesTo": "Module",
            "expression": {"operator": "<=", "left": {"path": "fanIn"}, "right": 10},
            "severity": "warning",
            "onViolation": {"action": "record"},
        },
        "action AddTests": {
            "inputs": {"module": {"type": "ref", "target": "Module"}},
            "effects": ["module.hasTests = true"],
            "rollback": ["module.hasTests = false"],
        },
        "action Decouple": {
            "inputs": {"module": {"type": "ref", "target": "Module"}},
            "effects": ["module.fanIn = 0"],
            "rollback": ["module.fanIn = 1"],
        },
        "transition HardenModule": {
            "action": "AddTests",
            "from": {"posture": "legacy"},
            "to": {"posture": "hardened"},
            "preserves": ["ModuleTested", "BoundedModule", "BoundedCoupling"],
        },
    }


def _sanitize_id(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return cleaned or "Unit"


def build_heuristic(survey: Survey, model_name: str) -> tuple[str, dict[str, Any]]:
    """Return (model_yaml, context) for a survey, with no external services."""
    ontology = _ontology(survey)
    model_yaml = yaml.safe_dump(ontology, sort_keys=False, default_flow_style=False)

    # Instances: one Module per discovered source unit, plus the System node.
    entities: dict[str, Any] = {
        "__system__": {"type": "System", "state": {"name": model_name}},
    }
    id_by_unitname: dict[str, str] = {}
    for unit in survey.units:
        inst_id = _sanitize_id(unit.name)
        # de-dupe instance ids
        base, n = inst_id, 2
        while inst_id in entities:
            inst_id, n = f"{base}_{n}", n + 1
        id_by_unitname[unit.name] = inst_id
        entities[inst_id] = {
            "type": "Module",
            "state": {
                "name": unit.name,
                "language": unit.language if unit.language in _language_values(survey) else "unknown",
                "lineCount": max(1, unit.size // 40),  # rough line estimate from chars
                "hasTests": survey.has_tests,
                "fanIn": 0,
            },
        }

    # dependsOn edges: a unit that mentions another unit's name depends on it.
    relationships: list[dict] = []
    fan_in: dict[str, int] = {}
    names = {u.name for u in survey.units}
    for path, text in survey.samples.items():
        # which unit owns this sample?
        owner = next((u.name for u in survey.units if u.path == path), None)
        if owner is None:
            continue
        for other in names:
            if other != owner and re.search(rf"\b{re.escape(other)}\b", text):
                relationships.append(
                    {"name": "dependsOn", "from": id_by_unitname[owner], "to": id_by_unitname[other]}
                )
                fan_in[other] = fan_in.get(other, 0) + 1
        if len(relationships) > 200:
            break
    # everything is part of the system
    for unit in survey.units:
        relationships.append({"name": "partOf", "from": id_by_unitname[unit.name], "to": "__system__"})
    # write computed fan-in back onto instances
    for unit_name, count in fan_in.items():
        entities[id_by_unitname[unit_name]]["state"]["fanIn"] = count

    context = {"entities": entities, "relationships": relationships}
    return model_yaml, context
