from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, FrozenSet, Generic, Hashable, Iterable, TypeVar

T = TypeVar("T", bound=Hashable)


@dataclass(frozen=True)
class FixedPointRound(Generic[T]):
    index: int
    before_size: int
    added: frozenset[T]
    after_size: int


@dataclass(frozen=True)
class FixedPointResult(Generic[T]):
    value: frozenset[T]
    rounds: tuple[FixedPointRound[T], ...]


def least_fixed_point(
    seed: Iterable[T],
    expand: Callable[[FrozenSet[T]], Iterable[T]],
    *,
    max_rounds: int | None = None,
) -> FixedPointResult[T]:
    """Audited monotone least fixed point over an explicit finite abstraction."""

    current = frozenset(seed)
    rounds: list[FixedPointRound[T]] = []
    index = 0
    while True:
        if max_rounds is not None and index >= max_rounds:
            raise RuntimeError("fixed point did not converge within max_rounds")
        proposed = frozenset(expand(current))
        if not current <= proposed:
            raise ValueError("closure transfer is not inflationary")
        added = proposed - current
        rounds.append(FixedPointRound(index, len(current), added, len(proposed)))
        if not added:
            return FixedPointResult(current, tuple(rounds))
        current = proposed
        index += 1
