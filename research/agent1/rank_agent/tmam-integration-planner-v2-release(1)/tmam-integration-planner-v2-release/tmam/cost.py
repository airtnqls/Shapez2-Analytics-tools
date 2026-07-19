from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterable, Protocol


@dataclass(frozen=True)
class CostVector:
    """Operation-independent cost vector used by all branches.

    New fields should be appended, not reordered, to preserve serialized data.
    """

    operations: int = 0
    buildings: int = 0
    inputs: int = 0
    pin_pushes: int = 0
    generators: int = 0
    stackers: int = 0
    swappers: int = 0
    cutters: int = 0
    rotators: int = 0
    painters: int = 0
    peak_height: int = 0
    auxiliary_cells: int = 0

    def __post_init__(self) -> None:
        if any(getattr(self, item.name) < 0 for item in fields(self)):
            raise ValueError("cost components must be nonnegative")

    def __add__(self, other: "CostVector") -> "CostVector":
        values = {
            item.name: getattr(self, item.name) + getattr(other, item.name)
            for item in fields(self)
        }
        values["peak_height"] = max(self.peak_height, other.peak_height)
        return CostVector(**values)

    @classmethod
    def sum(cls, costs: Iterable["CostVector"]) -> "CostVector":
        total = cls()
        for cost in costs:
            total = total + cost
        return total


class CostModel(Protocol):
    def combine(self, local: CostVector, children: tuple[CostVector, ...]) -> CostVector: ...

    def ordering_key(self, cost: CostVector) -> tuple[int, ...]: ...


@dataclass(frozen=True)
class LexicographicCostModel:
    """Default deterministic policy.

    The order can be replaced without touching any relation provider.
    """

    order: tuple[str, ...] = (
        "operations",
        "buildings",
        "inputs",
        "pin_pushes",
        "generators",
        "stackers",
        "swappers",
        "cutters",
        "rotators",
        "painters",
        "peak_height",
        "auxiliary_cells",
    )

    def combine(self, local: CostVector, children: tuple[CostVector, ...]) -> CostVector:
        return local + CostVector.sum(children)

    def ordering_key(self, cost: CostVector) -> tuple[int, ...]:
        return tuple(getattr(cost, name) for name in self.order)


@dataclass(frozen=True)
class CriticalPathCostModel(LexicographicCostModel):
    """Parallel-production model: local work plus the slowest child branch."""

    def combine(self, local: CostVector, children: tuple[CostVector, ...]) -> CostVector:
        if not children:
            return local
        slowest = max(children, key=self.ordering_key)
        return local + slowest
