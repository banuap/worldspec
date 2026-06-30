"""Model registry — register/activate compiled WorldSpec packages.

Loads the IR straight out of a ``.wspkg`` (a zip) without importing the compiler,
keeping the runtime independent of it (ADR-003). The in-memory registry is the
v0.1 implementation of §11.1; a persistent store would sit behind the same API.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Optional

from worldspec.runtime.errors import ModelNotFound
from worldspec.runtime.model import RuntimeModel


def load_ir_from_package(path: str | Path) -> dict[str, Any]:
    """Read ``ontology.json`` (the canonical IR) out of a .wspkg archive."""
    path = Path(path)
    if not path.exists():
        raise ModelNotFound(f"Package not found: {path}")
    with zipfile.ZipFile(path, "r") as zf:
        return json.loads(zf.read("ontology.json"))


def load_model_from_package(path: str | Path) -> RuntimeModel:
    return RuntimeModel.from_ir(load_ir_from_package(path))


class ModelRegistry:
    """Registers compiled models by name + version and tracks the active one."""

    def __init__(self) -> None:
        # name -> {version -> RuntimeModel}
        self._models: dict[str, dict[str, RuntimeModel]] = {}
        self._active: dict[str, str] = {}

    def register(self, model: RuntimeModel, *, version: str = "0.1.0", activate: bool = True) -> None:
        versions = self._models.setdefault(model.name, {})
        versions[version] = model
        if activate or model.name not in self._active:
            self._active[model.name] = version

    def register_package(self, path: str | Path, *, version: str = "0.1.0") -> RuntimeModel:
        model = load_model_from_package(path)
        self.register(model, version=version)
        return model

    def activate(self, name: str, version: str) -> None:
        if name not in self._models or version not in self._models[name]:
            raise ModelNotFound(f"No registered model {name}@{version}")
        self._active[name] = version

    def get(self, name: str, version: Optional[str] = None) -> RuntimeModel:
        if name not in self._models:
            raise ModelNotFound(f"Model '{name}' is not registered")
        version = version or self._active.get(name)
        if version not in self._models[name]:
            raise ModelNotFound(f"No registered version {version} of model '{name}'")
        return self._models[name][version]

    def list_models(self) -> dict[str, list[str]]:
        return {name: sorted(vers) for name, vers in self._models.items()}
