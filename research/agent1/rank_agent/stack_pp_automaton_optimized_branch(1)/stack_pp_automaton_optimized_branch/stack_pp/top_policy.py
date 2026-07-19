from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AnyTopPiecePolicy:
    """Accept every non-empty visible, crystal-free Stack layer piece."""

    name: str = "any-visible-top-piece"

    def accepts(self, row_signature: tuple[int, int, int, int]) -> bool:
        occupied, crystal, _pin, _ordinary = row_signature
        return occupied != 0 and crystal == 0


@dataclass(frozen=True)
class PredicateTopPiecePolicy:
    """Adapter for a proven local one-layer input-family predicate."""

    name: str
    predicate: Callable[[tuple[int, int, int, int]], bool]

    def accepts(self, row_signature: tuple[int, int, int, int]) -> bool:
        return bool(self.predicate(row_signature))
