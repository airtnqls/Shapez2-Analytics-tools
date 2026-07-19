from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Generic, Iterable, TypeVar

from .contracts import ForwardModel, ShapeBackend
from .planner import PlannerConfig, TMAMPlanner
from .registry import IntegrationRegistry
from .runtime import TMAMRuntime

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class BootstrapResult(Generic[ShapeT]):
    runtime: TMAMRuntime[ShapeT]
    loaded_plugins: tuple[str, ...]


def load_plugins(registry: IntegrationRegistry, modules: Iterable[str]) -> tuple[str, ...]:
    loaded: list[str] = []
    for module_name in modules:
        module = importlib.import_module(module_name)
        register = getattr(module, "register_tmam_plugin", None)
        if register is None:
            raise RuntimeError(f"{module_name} has no register_tmam_plugin(registry)")
        register(registry)
        loaded.append(module_name)
    errors = registry.validate_plugins()
    if errors:
        raise RuntimeError("plugin validation failed: " + "; ".join(errors))
    return tuple(loaded)


def build_runtime(
    *,
    backend: ShapeBackend[ShapeT],
    forward: ForwardModel[ShapeT],
    plugin_modules: Iterable[str],
    required_relation_ids: frozenset[str],
) -> BootstrapResult[ShapeT]:
    registry: IntegrationRegistry[ShapeT] = IntegrationRegistry()
    loaded = load_plugins(registry, plugin_modules)
    planner = TMAMPlanner(
        backend=backend,
        registry=registry,
        config=PlannerConfig(required_relation_ids=required_relation_ids),
        forward=forward,
    )
    return BootstrapResult(
        runtime=TMAMRuntime(backend=backend, forward=forward, planner=planner),
        loaded_plugins=loaded,
    )
