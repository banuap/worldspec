"""Artifact generators (§9.4).

For v0.1 we generate the artifacts the runtime and CI actually consume:

* JSON Schema (one schema per entity, for instance validation),
* a model manifest,
* a ``.wspkg`` package (a zip containing manifest.json, ontology.json,
  schemas/, docs/).

Other generators listed in the instructions (Neo4j constraints, SHACL, GraphQL,
OpenAPI) are deferred until the runtime that needs them lands (operating rule 4:
no speculative abstractions). Their absence is recorded in
``docs/open-questions.md``.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from worldspec import COMPILER_VERSION, LANGUAGE_VERSION, PACKAGE_FORMAT_VERSION
from worldspec.compiler.ast import Entity, Model, TypeDecl

_JSON_SCHEMA_TYPES = {
    "string": {"type": "string"},
    "int": {"type": "integer"},
    "float": {"type": "number"},
    "bool": {"type": "boolean"},
    "datetime": {"type": "string", "format": "date-time"},
}


def _property_schema(td: TypeDecl) -> dict[str, Any]:
    if td.type == "enum":
        return {"enum": list(td.values or [])}
    if td.type == "ref":
        return {
            "type": "string",
            "description": f"identity reference to entity {td.target}",
        }
    return dict(_JSON_SCHEMA_TYPES[td.type])


def entity_json_schema(entity: Entity, model_name: str) -> dict[str, Any]:
    properties = {
        name: _property_schema(td) for name, td in entity.properties.items()
    }
    required = sorted(
        {name for name, td in entity.properties.items() if td.required}
        | set(entity.identity)
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"worldspec:{model_name}/{entity.name}",
        "title": entity.name,
        "description": entity.description or "",
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def generate_json_schemas(model: Model) -> dict[str, dict[str, Any]]:
    return {
        name: entity_json_schema(ent, model.name)
        for name, ent in model.entities.items()
    }


def generate_manifest(model: Model, ir: dict[str, Any]) -> dict[str, Any]:
    counts = {
        "entity": len(model.entities),
        "relationship": len(model.relationships),
        "state": len(model.states),
        "invariant": len(model.invariants),
        "action": len(model.actions),
        "transition": len(model.transitions),
    }
    return {
        "name": model.name,
        "packageFormatVersion": PACKAGE_FORMAT_VERSION,
        "languageVersion": LANGUAGE_VERSION,
        "compilerVersion": COMPILER_VERSION,
        "irVersion": ir.get("irVersion"),
        "constructCounts": counts,
        "constructs": sorted(model.all_construct_names()),
    }


def build_package(model: Model, ir: dict[str, Any], output: str | Path) -> Path:
    """Write a ``.wspkg`` (zip) with manifest, ontology IR, schemas, and docs."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = generate_manifest(model, ir)
    schemas = generate_json_schemas(model)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        zf.writestr("ontology.json", json.dumps(ir, indent=2, sort_keys=True))
        for name, schema in schemas.items():
            zf.writestr(
                f"schemas/{name}.schema.json",
                json.dumps(schema, indent=2, sort_keys=True),
            )
        zf.writestr("docs/README.txt", _package_readme(model, manifest))
    return output


def read_package(path: str | Path) -> dict[str, Any]:
    """Read back a ``.wspkg`` for ``worldspec inspect``."""
    path = Path(path)
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        ontology = json.loads(zf.read("ontology.json"))
        schema_names = sorted(
            n.split("/", 1)[1].replace(".schema.json", "")
            for n in zf.namelist()
            if n.startswith("schemas/")
        )
    return {"manifest": manifest, "ontology": ontology, "schemas": schema_names}


def _package_readme(model: Model, manifest: dict[str, Any]) -> str:
    lines = [
        f"WorldSpec package: {model.name}",
        f"Package format: {manifest['packageFormatVersion']}",
        f"Language: {manifest['languageVersion']}  Compiler: {manifest['compilerVersion']}",
        "",
        "Construct counts:",
    ]
    for kind, n in manifest["constructCounts"].items():
        lines.append(f"  {kind:<13} {n}")
    return "\n".join(lines) + "\n"
