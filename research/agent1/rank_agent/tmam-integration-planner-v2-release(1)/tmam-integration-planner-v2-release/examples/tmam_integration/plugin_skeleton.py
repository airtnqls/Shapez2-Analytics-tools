"""Template for core-kernel, corner-half, generator, or stack-pp branches."""
from __future__ import annotations

from tmam import PluginManifest


def register_tmam_plugin(registry) -> None:
    # registry.register_relation(MyExactRelation(...))
    # registry.register_family(MySymbolicFamily(...))
    registry.register_plugin(
        PluginManifest(
            plugin_id="replace-me",
            version="0.1.0",
            provides_relations=frozenset(),
            provides_families=frozenset(),
            requires_plugins=frozenset({"core-kernel"}),
        )
    )
