from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Hashable, TypeVar

from .model import FamilyWitness

ShapeT = TypeVar("ShapeT", bound=Hashable)


@dataclass(frozen=True)
class PredicateFamily(Generic[ShapeT]):
    """Small adapter used during integration and tests.

    The final Half family should expose a symbolic automaton directly, but its
    public membership surface is intentionally identical to this class.
    """

    name: str
    predicate: Callable[[ShapeT], bool]
    witness_factory: Callable[[ShapeT], object | None] | None = None

    def contains(self, shape: ShapeT) -> bool:
        return bool(self.predicate(shape))

    def witness(self, shape: ShapeT) -> FamilyWitness[ShapeT] | None:
        if not self.contains(shape):
            return None
        payload = self.witness_factory(shape) if self.witness_factory else None
        return FamilyWitness(self.name, shape, payload)


@dataclass(frozen=True)
class UnionFamily(Generic[ShapeT]):
    """Finite union of already-proved families."""

    name: str
    families: tuple[object, ...]

    def contains(self, shape: ShapeT) -> bool:
        return any(family.contains(shape) for family in self.families)

    def witness(self, shape: ShapeT) -> FamilyWitness[ShapeT] | None:
        for family in self.families:
            witness = family.witness(shape)
            if witness is not None:
                return FamilyWitness(
                    self.name,
                    shape,
                    {"member_family": family.name, "witness": witness},
                )
        return None


@dataclass(frozen=True)
class RankedPPFamily(Generic[ShapeT]):
    """Family view over retained PP entries up to a strict rank ceiling."""

    result: object
    max_rank_exclusive: int
    name: str = "lower-rank-pp"
    include_globally_redundant: bool = True

    def contains(self, shape: ShapeT) -> bool:
        entry = self.result.entries.get(shape)
        if entry is None or entry.discovery_rank >= self.max_rank_exclusive:
            return False
        if not self.include_globally_redundant and shape in self.result.global_redundant:
            return False
        return True

    def witness(self, shape: ShapeT) -> FamilyWitness[ShapeT] | None:
        if not self.contains(shape):
            return None
        entry = self.result.entries[shape]
        return FamilyWitness(
            self.name,
            shape,
            {
                "discovery_rank": entry.discovery_rank,
                "pinpush_parent": entry.parent,
                "globally_redundant": shape in self.result.global_redundant,
            },
        )
