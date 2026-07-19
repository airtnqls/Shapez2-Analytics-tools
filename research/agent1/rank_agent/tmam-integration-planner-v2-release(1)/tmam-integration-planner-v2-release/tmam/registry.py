from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, TypeVar

from .contracts import InverseRelation, PluginManifest, ShapeFamily
from .enums import Operation

ShapeT = TypeVar("ShapeT")


class RegistryError(RuntimeError):
    pass


@dataclass
class IntegrationRegistry(Generic[ShapeT]):
    relations: dict[str, InverseRelation[ShapeT]] = field(default_factory=dict)
    families: dict[str, ShapeFamily[ShapeT]] = field(default_factory=dict)
    plugins: dict[str, PluginManifest] = field(default_factory=dict)
    _generation: int = field(default=0, init=False, repr=False)

    @property
    def generation(self) -> int:
        """Monotone cache-invalidation generation."""

        return self._generation

    def _touch(self) -> None:
        self._generation += 1

    def register_relation(self, relation: InverseRelation[ShapeT]) -> None:
        if relation.provider_id in self.relations:
            raise RegistryError(f"duplicate relation provider: {relation.provider_id}")
        self.relations[relation.provider_id] = relation
        self._touch()

    def unregister_relation(self, provider_id: str) -> None:
        if self.relations.pop(provider_id, None) is not None:
            self._touch()

    def register_family(self, family: ShapeFamily[ShapeT]) -> None:
        if family.family_id in self.families:
            raise RegistryError(f"duplicate family provider: {family.family_id}")
        self.families[family.family_id] = family
        self._touch()

    def register_plugin(self, manifest: PluginManifest) -> None:
        if manifest.plugin_id in self.plugins:
            raise RegistryError(f"duplicate plugin: {manifest.plugin_id}")
        self.plugins[manifest.plugin_id] = manifest
        self._touch()

    def validate_plugins(self) -> tuple[str, ...]:
        errors: list[str] = []
        for manifest in self.plugins.values():
            missing = manifest.requires_plugins - self.plugins.keys()
            if missing:
                errors.append(f"{manifest.plugin_id}: missing plugins {sorted(missing)}")
            missing_relations = manifest.provides_relations - self.relations.keys()
            if missing_relations:
                errors.append(
                    f"{manifest.plugin_id}: manifest relations not registered {sorted(missing_relations)}"
                )
            missing_families = manifest.provides_families - self.families.keys()
            if missing_families:
                errors.append(
                    f"{manifest.plugin_id}: manifest families not registered {sorted(missing_families)}"
                )
        return tuple(errors)

    def relations_for(self, operation: Operation) -> tuple[InverseRelation[ShapeT], ...]:
        return tuple(
            sorted(
                (relation for relation in self.relations.values() if relation.operation is operation),
                key=lambda relation: (relation.priority, relation.provider_id),
            )
        )

    def ordered_relations(self) -> tuple[InverseRelation[ShapeT], ...]:
        return tuple(
            sorted(self.relations.values(), key=lambda relation: (relation.priority, relation.provider_id))
        )

    def missing_required_relations(self, required: Iterable[str]) -> frozenset[str]:
        return frozenset(required) - self.relations.keys()
