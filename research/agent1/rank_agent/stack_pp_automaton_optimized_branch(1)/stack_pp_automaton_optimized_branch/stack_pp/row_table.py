from __future__ import annotations

"""Compact exact tables for the 256 structural quad rows.

A row id is the base-four encoding ``q0 q1 q2 q3`` where each cell is
EMPTY=0, NORMAL=1, PIN=2, CRYSTAL=3.  The encoding order matches
``itertools.product(range(4), repeat=4)`` and the generated support quotient.
"""

from .rows import CRYSTAL, EMPTY, NORMAL, PIN, RowInfo, landing_row_is_valid

ROW_COUNT = 256
ROW_INF = 256


def row_id_from_cells(cells: tuple[int, int, int, int]) -> int:
    q0, q1, q2, q3 = cells
    return (q0 << 6) | (q1 << 4) | (q2 << 2) | q3


def cells_from_row_id(row_id: int) -> tuple[int, int, int, int]:
    if not 0 <= row_id < ROW_COUNT:
        raise ValueError(f"row id outside [0,255]: {row_id}")
    return (
        (row_id >> 6) & 3,
        (row_id >> 4) & 3,
        (row_id >> 2) & 3,
        row_id & 3,
    )


ROW_INFO: tuple[RowInfo, ...] = tuple(
    RowInfo.from_cells(cells_from_row_id(row_id)) for row_id in range(ROW_COUNT)
)
ROW_SIGNATURES: tuple[tuple[int, int, int, int], ...] = tuple(
    row.as_signature() for row in ROW_INFO
)
ROW_OCCUPIED = bytes(row.occupied for row in ROW_INFO)
ROW_CRYSTAL = bytes(row.crystal for row in ROW_INFO)
ROW_PIN = bytes(row.pin for row in ROW_INFO)
ROW_ORDINARY = bytes(row.ordinary for row in ROW_INFO)

_SIGNATURE_TO_ROW_ID = {signature: row_id for row_id, signature in enumerate(ROW_SIGNATURES)}


def row_id_from_signature(signature: tuple[int, int, int, int]) -> int:
    try:
        return _SIGNATURE_TO_ROW_ID[tuple(int(value) for value in signature)]
    except KeyError as exc:
        raise ValueError(f"invalid/redundant structural row signature: {signature!r}") from exc


def row_id_from_info(row: RowInfo) -> int:
    return row_id_from_signature(row.as_signature())


PROJECT_ROW_ID: tuple[bytes, ...] = tuple(
    bytes(
        row_id_from_info(ROW_INFO[row_id].project(keep_mask))
        for keep_mask in range(16)
    )
    for row_id in range(ROW_COUNT)
)

SUBMASKS: tuple[tuple[int, ...], ...] = tuple(
    tuple(
        subset
        for subset in range(16)
        if subset & ~mask == 0
    )
    for mask in range(16)
)

# For every target row and visible-B mask, store a 16-bit set of the full-row
# occupancy masks below which the B row lands exactly at this height.
LANDING_BELOW_SET: tuple[tuple[int, ...], ...] = tuple(
    tuple(
        sum(
            1 << below
            for below in range(16)
            if landing_row_is_valid(
                is_floor=False,
                b_mask=b_mask,
                row=ROW_INFO[row_id],
                below_occupied=below,
            )
        )
        for b_mask in range(16)
    )
    for row_id in range(ROW_COUNT)
)


def landing_valid(row_id: int, b_mask: int, below_occupied: int, is_floor: bool) -> bool:
    return is_floor or bool(
        LANDING_BELOW_SET[row_id][b_mask & 15] & (1 << (below_occupied & 15))
    )
