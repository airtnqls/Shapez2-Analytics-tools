from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

EMPTY = 0
NORMAL = 1
PIN = 2
CRYSTAL = 3
ADJACENT = ((1, 3), (0, 2), (1, 3), (0, 2))


@dataclass(frozen=True)
class RowInfo:
    occupied: int
    crystal: int
    pin: int
    ordinary: int

    @classmethod
    def from_cells(cls, cells: Iterable[int]) -> "RowInfo":
        values = tuple(cells)
        if len(values) != 4:
            raise ValueError("a Shapez2 quad row must contain exactly four cells")
        occupied = crystal = pin = ordinary = 0
        for q, value in enumerate(values):
            bit = 1 << q
            if value == EMPTY:
                continue
            if value not in (NORMAL, PIN, CRYSTAL):
                raise ValueError(f"invalid structural cell value {value}")
            occupied |= bit
            if value == CRYSTAL:
                crystal |= bit
            elif value == PIN:
                pin |= bit
            else:
                ordinary |= bit
        return cls(occupied, crystal, pin, ordinary)

    def project(self, keep_mask: int) -> "RowInfo":
        keep = keep_mask & 15
        return RowInfo(
            self.occupied & keep,
            self.crystal & keep,
            self.pin & keep,
            self.ordinary & keep,
        )

    def as_signature(self) -> tuple[int, int, int, int]:
        return self.occupied, self.crystal, self.pin, self.ordinary


@lru_cache(maxsize=16)
def ordinary_components(mask: int) -> tuple[int, ...]:
    components: list[int] = []
    remaining = mask & 15
    while remaining:
        start = (remaining & -remaining).bit_length() - 1
        stack = [start]
        component = 0
        while stack:
            q = stack.pop()
            bit = 1 << q
            if component & bit or not remaining & bit:
                continue
            component |= bit
            for neighbor in ADJACENT[q]:
                nbit = 1 << neighbor
                if remaining & nbit and not component & nbit:
                    stack.append(neighbor)
        components.append(component)
        remaining &= ~component
    return tuple(components)


def landing_row_is_valid(
    *,
    is_floor: bool,
    b_mask: int,
    row: RowInfo,
    below_occupied: int,
) -> bool:
    if b_mask == 0 or is_floor:
        return True
    b_pins = row.pin & b_mask
    if b_pins & ~below_occupied:
        return False
    b_ordinary = row.ordinary & b_mask
    return all(component & below_occupied for component in ordinary_components(b_ordinary))
