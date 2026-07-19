from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .model import (
    FamilyWitness,
    PPEntry,
    PPSeed,
    StackCertificate,
    StackClosureNode,
)


@dataclass
class FiniteStringDomain:
    """Reference PP domain loaded from a small fixed-cap concrete oracle.

    This class is not the all-layer implementation.  It exists so cpcp or a
    brute-force small-L exporter can be compared against exactly the same rank
    engine used by the future symbolic backend.
    """

    base_seeds: tuple[str, ...]
    closures: Mapping[str, tuple[tuple[str, object | None], ...]]
    pin_push_map: Mapping[str, str]
    swappable: frozenset[str]
    stack_parents: Mapping[str, tuple[tuple[str, str], ...]]
    progress: Mapping[str, tuple]

    @classmethod
    def from_json_dict(cls, data: Mapping[str, object]) -> "FiniteStringDomain":
        closures = {
            str(seed): tuple((str(row[0]), row[1] if len(row) > 1 else None) for row in rows)
            for seed, rows in dict(data.get("closures", {})).items()
        }
        stack_parents = {
            str(target): tuple((str(row[0]), str(row[1])) for row in rows)
            for target, rows in dict(data.get("stack_parents", {})).items()
        }
        progress = {
            str(shape): tuple(value if isinstance(value, list) else [value])
            for shape, value in dict(data.get("progress", {})).items()
        }
        return cls(
            base_seeds=tuple(map(str, data.get("base_seeds", ()))),
            closures=closures,
            pin_push_map={
                str(k): str(v) for k, v in dict(data.get("pin_push", {})).items()
            },
            swappable=frozenset(map(str, data.get("swappable", ()))),
            stack_parents=stack_parents,
            progress=progress,
        )

    def seeds_for_batch(
        self,
        batch: int,
        previous_batch: tuple[PPEntry[str], ...],
        retained: dict[str, PPEntry[str]],
    ) -> Iterable[PPSeed[str]]:
        del retained
        if batch == 0:
            return tuple(PPSeed(shape, -1, "base") for shape in self.base_seeds)
        return tuple(
            PPSeed(entry.shape, entry.discovery_rank, "pp")
            for entry in previous_batch
        )

    def stack_closure(self, seed: PPSeed[str]):
        return tuple(
            StackClosureNode(shape, trace)
            for shape, trace in self.closures.get(seed.shape, ())
        )

    def pin_push(self, predecessor: str) -> str:
        return self.pin_push_map[predecessor]

    def canonical(self, shape: str) -> str:
        return shape

    def is_empty(self, shape: str) -> bool:
        return shape == ""

    def is_swappable(self, shape: str) -> bool:
        return shape in self.swappable

    def stack_witness(self, target: str, allowed_base):
        for bottom, top in self.stack_parents.get(target, ()):
            if not allowed_base(bottom):
                continue
            return StackCertificate(
                target=target,
                bottom=bottom,
                top=top,
                bottom_family="allowed-base",
                top_family="finite-top-piece",
                bottom_witness=FamilyWitness("allowed-base", bottom),
                top_witness=FamilyWitness("finite-top-piece", top),
                backend_payload={"oracle": "finite-string"},
            )
        return None

    def progress_key(self, shape: str) -> tuple:
        return self.progress.get(shape, (10**9, shape))

    def order_key(self, shape: str) -> tuple:
        return (shape,)
