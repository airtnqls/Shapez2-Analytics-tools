"""Small immutable lookup tables for the four-cell layer alphabet."""
from __future__ import annotations

from .model import CRYSTAL, EMPTY, NORMAL, PIN, WIDTH

ROW_CELLS: list[tuple[int, int, int, int]] = []
ROW_OCC: list[int] = []
ROW_NORMAL: list[int] = []
ROW_PIN: list[int] = []
ROW_CRYSTAL: list[int] = []
ROW_ROT_CW: list[int] = []
ROW_ROT_CCW: list[int] = []
ROW_ROT_180: list[int] = []
ROW_MIRROR_CPCP: list[int] = []
ROW_MIRROR_PROJECT: list[int] = []


def _encode(values: tuple[int, int, int, int]) -> int:
    row = 0
    for column, value in enumerate(values):
        row |= value << (2 * column)
    return row


for row in range(256):
    values = tuple((row >> (2 * column)) & 3 for column in range(WIDTH))
    ROW_CELLS.append(values)  # type: ignore[arg-type]
    occ = normal = pin = crystal = 0
    for column, value in enumerate(values):
        bit = 1 << column
        if value != EMPTY:
            occ |= bit
        if value == NORMAL:
            normal |= bit
        elif value == PIN:
            pin |= bit
        elif value == CRYSTAL:
            crystal |= bit
    ROW_OCC.append(occ)
    ROW_NORMAL.append(normal)
    ROW_PIN.append(pin)
    ROW_CRYSTAL.append(crystal)
    ROW_ROT_CW.append(_encode((values[3], values[0], values[1], values[2])))
    ROW_ROT_CCW.append(_encode((values[1], values[2], values[3], values[0])))
    ROW_ROT_180.append(_encode((values[2], values[3], values[0], values[1])))
    # cpcp's q -> 3-q reflection.  Any one reflection plus rotations spans D4.
    ROW_MIRROR_CPCP.append(_encode((values[3], values[2], values[1], values[0])))
    # Existing Shapez2-Analytics-tools mirror [0,3,2,1].
    ROW_MIRROR_PROJECT.append(_encode((values[0], values[3], values[2], values[1])))


ADJACENT = ((1, 3), (0, 2), (1, 3), (0, 2))


def _components(mask: int) -> tuple[int, ...]:
    remaining = mask & 0xF
    output: list[int] = []
    while remaining:
        start_bit = remaining & -remaining
        start = start_bit.bit_length() - 1
        stack = [start]
        component = 0
        while stack:
            column = stack.pop()
            bit = 1 << column
            if not (remaining & bit):
                continue
            remaining &= ~bit
            component |= bit
            for neighbor in ADJACENT[column]:
                if remaining & (1 << neighbor):
                    stack.append(neighbor)
        output.append(component)
    return tuple(output)


RING_COMPONENTS = tuple(_components(mask) for mask in range(16))
