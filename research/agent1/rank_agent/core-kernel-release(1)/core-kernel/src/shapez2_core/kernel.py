"""Exact structural physics and forward operations.

The semantics mirror cpcp1998/shapez2-solver's `Shape` implementation:

1. least support fixed point,
2. delete unsupported crystals,
3. bottom-up one-layer horizontal fall groups.

All functions are pure.  They accept and return :class:`CompactShape` values.
"""
from __future__ import annotations

from collections import deque
from enum import IntEnum
from typing import Iterable, Iterator, Sequence

from .model import (
    BITS_PER_LAYER,
    CRYSTAL,
    EMPTY,
    PIN,
    ROW_MASK,
    WIDTH,
    CompactShape,
    cap_mask,
    put_cell,
)
from .tables import (
    ADJACENT,
    RING_COMPONENTS,
    ROW_CELLS,
    ROW_CRYSTAL,
    ROW_MIRROR_CPCP,
    ROW_MIRROR_PROJECT,
    ROW_OCC,
    ROW_PIN,
    ROW_ROT_180,
    ROW_ROT_CCW,
    ROW_ROT_CW,
)


class CutAxis(IntEnum):
    VERTICAL = 0   # east (0,1) / west (2,3)
    HORIZONTAL = 1 # north (3,0) / south (1,2)


EAST_COLUMNS = 0b0011
WEST_COLUMNS = 0b1100
NORTH_COLUMNS = 0b1001
SOUTH_COLUMNS = 0b0110


def _position_bit(layer: int, column: int) -> int:
    return 1 << (WIDTH * layer + column)


def _iter_position_bits(mask: int) -> Iterator[int]:
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit


def _position_from_bit(bit: int) -> tuple[int, int]:
    index = bit.bit_length() - 1
    return divmod(index, WIDTH)


def _rows_from_shape(shape: CompactShape) -> list[int]:
    height = shape.height
    return list(shape.bits.to_bytes(height, "little")) if height else []


def _bits_from_rows(rows: Sequence[int], cap: int) -> int:
    materialized = bytes(int(row) & ROW_MASK for row in rows[:cap])
    return int.from_bytes(materialized, "little") if materialized else 0


def _support_masks(rows: Sequence[int]) -> list[int]:
    """Least support fixed point as one four-bit mask per layer."""
    height = len(rows)
    if height == 0:
        return []
    occupied = [ROW_OCC[row] for row in rows]
    pin = [ROW_PIN[row] for row in rows]
    crystal = [ROW_CRYSTAL[row] for row in rows]
    supported = [0] * height
    supported[0] = occupied[0]
    queue: deque[tuple[int, int]] = deque(
        (0, column) for column in range(WIDTH) if occupied[0] & (1 << column)
    )

    def add(layer: int, column: int) -> None:
        bit = 1 << column
        if not supported[layer] & bit:
            supported[layer] |= bit
            queue.append((layer, column))

    while queue:
        layer, column = queue.popleft()
        bit = 1 << column

        # Any occupied cell directly above supported material is supported.
        if layer + 1 < height and occupied[layer + 1] & bit:
            add(layer + 1, column)

        # Horizontal support passes between adjacent non-pin cells.
        if not pin[layer] & bit:
            for neighbor in ADJACENT[column]:
                nbit = 1 << neighbor
                if occupied[layer] & nbit and not pin[layer] & nbit:
                    add(layer, neighbor)

        # Crystal below a supported crystal hangs from it.
        if layer > 0 and crystal[layer] & bit and crystal[layer - 1] & bit:
            add(layer - 1, column)

    return supported


def occupied_positions(shape: CompactShape) -> int:
    result = 0
    for layer, row in enumerate(_rows_from_shape(shape)):
        result |= ROW_OCC[row] << (WIDTH * layer)
    return result


def crystal_positions(shape: CompactShape) -> int:
    result = 0
    for layer, row in enumerate(_rows_from_shape(shape)):
        result |= ROW_CRYSTAL[row] << (WIDTH * layer)
    return result


def support_positions(shape: CompactShape) -> int:
    result = 0
    for layer, mask in enumerate(_support_masks(_rows_from_shape(shape))):
        result |= mask << (WIDTH * layer)
    return result


def is_stable(shape: CompactShape) -> bool:
    return apply_gravity(shape).bits == shape.bits


def _clear_position_bits(bits: int, positions: int) -> int:
    for bit in _iter_position_bits(positions):
        layer, column = _position_from_bit(bit)
        bits = put_cell(bits, layer, column, EMPTY)
    return bits


def crystal_component_positions(
    shape: CompactShape, seeds: Iterable[tuple[int, int]]
) -> int:
    """Return all crystal cells 4-connected to crystal seeds."""
    rows = _rows_from_shape(shape)
    height = len(rows)
    crystal_masks = [ROW_CRYSTAL[row] for row in rows]
    seen_masks = [0] * height
    queue: deque[tuple[int, int]] = deque()
    for layer, column in seeds:
        if 0 <= layer < height:
            bit = 1 << column
            if crystal_masks[layer] & bit and not seen_masks[layer] & bit:
                seen_masks[layer] |= bit
                queue.append((layer, column))
    while queue:
        layer, column = queue.popleft()
        for neighbor in ADJACENT[column]:
            bit = 1 << neighbor
            if crystal_masks[layer] & bit and not seen_masks[layer] & bit:
                seen_masks[layer] |= bit
                queue.append((layer, neighbor))
        bit = 1 << column
        for next_layer in (layer - 1, layer + 1):
            if (
                0 <= next_layer < height
                and crystal_masks[next_layer] & bit
                and not seen_masks[next_layer] & bit
            ):
                seen_masks[next_layer] |= bit
                queue.append((next_layer, column))
    result = 0
    for layer, mask in enumerate(seen_masks):
        result |= mask << (WIDTH * layer)
    return result


def shatter_crystals(
    shape: CompactShape, seeds: Iterable[tuple[int, int]]
) -> CompactShape:
    positions = crystal_component_positions(shape, seeds)
    if not positions:
        return shape
    rows = _rows_from_shape(shape)
    for layer in range(len(rows)):
        mask = (positions >> (WIDTH * layer)) & 0xF
        if not mask:
            continue
        row = rows[layer]
        for column in range(WIDTH):
            if mask & (1 << column):
                row &= ~(0b11 << (2 * column))
        rows[layer] = row
    return CompactShape(_bits_from_rows(rows, shape.cap), shape.cap)


def apply_gravity(shape: CompactShape) -> CompactShape:
    """Apply the exact single gravity pass used by the game operations.

    The packed implementation decodes only one byte per occupied layer.  All
    inner state thereafter uses four-bit row masks, avoiding repeated large
    integer shifts while retaining an immutable external representation.
    """
    rows = _rows_from_shape(shape)
    height = len(rows)
    if height == 0:
        return shape

    supported = _support_masks(rows)

    # Remove unsupported crystals.  Every crystal component is support-uniform,
    # because vertical/horizontal crystal adjacency itself propagates support.
    for layer in range(height):
        unsupported = ROW_CRYSTAL[rows[layer]] & ~supported[layer] & 0xF
        if unsupported:
            row = rows[layer]
            for column in range(WIDTH):
                if unsupported & (1 << column):
                    row &= ~(0b11 << (2 * column))
            rows[layer] = row

    # Highest settled cell below the current source layer.  Because the fall
    # sweep is bottom-up and groups at one layer use disjoint columns, this
    # four-entry frontier is sufficient; no per-layer predecessor search is
    # needed.
    settled_top = [
        0 if ROW_OCC[rows[0]] & (1 << column) else -1
        for column in range(WIDTH)
    ]

    dropped = [0] * height
    for layer in range(1, height):
        for start_column in range(WIDTH):
            start_bit = 1 << start_column
            row = rows[layer]
            value = (row >> (2 * start_column)) & 3
            if (
                value == EMPTY
                or supported[layer] & start_bit
                or dropped[layer] & start_bit
            ):
                continue

            if value == PIN:
                group_mask = start_bit
            else:
                eligible = ROW_OCC[row] & ~ROW_PIN[row] & ~supported[layer] & 0xF
                group_mask = next(
                    component
                    for component in RING_COMPONENTS[eligible]
                    if component & start_bit
                )

            dropped[layer] |= group_mask
            group_columns = [
                column for column in range(WIDTH) if group_mask & (1 << column)
            ]
            min_drop = min(
                layer - settled_top[column] - 1 for column in group_columns
            )
            if min_drop <= 0:
                continue

            target_layer = layer - min_drop
            source_row = rows[layer]
            target_row = rows[target_layer]
            for column in group_columns:
                shift = 2 * column
                piece = (source_row >> shift) & 3
                source_row &= ~(0b11 << shift)
                target_row = (target_row & ~(0b11 << shift)) | (piece << shift)
                settled_top[column] = max(settled_top[column], target_layer)
            rows[layer] = source_row
            rows[target_layer] = target_row

        # Anything still present at this source layer is now final and becomes
        # the nearest settled support for later layers in that column.
        remaining = ROW_OCC[rows[layer]]
        for column in range(WIDTH):
            if remaining & (1 << column):
                settled_top[column] = layer

    return CompactShape(_bits_from_rows(rows, shape.cap), shape.cap)


def rotate(shape: CompactShape, turns: int = 1) -> CompactShape:
    turns %= WIDTH
    if turns == 0 or shape.bits == 0:
        return shape
    table = (None, ROW_ROT_CW, ROW_ROT_180, ROW_ROT_CCW)[turns]
    assert table is not None
    rows = _rows_from_shape(shape)
    return CompactShape(_bits_from_rows([table[row] for row in rows], shape.cap), shape.cap)


def mirror(shape: CompactShape, *, project_axis: bool = False) -> CompactShape:
    table = ROW_MIRROR_PROJECT if project_axis else ROW_MIRROR_CPCP
    rows = _rows_from_shape(shape)
    return CompactShape(_bits_from_rows([table[row] for row in rows], shape.cap), shape.cap)


def dihedral_variants(shape: CompactShape) -> tuple[CompactShape, ...]:
    variants: list[CompactShape] = []
    current = shape
    for _ in range(WIDTH):
        variants.append(current)
        variants.append(mirror(current))
        current = rotate(current)
    # Deduplicate symmetric shapes without changing deterministic order.
    return tuple(dict.fromkeys(variants))


def canonical_with_transform(
    shape: CompactShape,
) -> tuple[CompactShape, int, bool]:
    """Return canonical shape plus ``(clockwise_turns, mirrored)`` witness."""
    candidates: list[tuple[CompactShape, int, bool]] = []
    current = shape
    for turns in range(WIDTH):
        candidates.append((current, turns, False))
        candidates.append((mirror(current), turns, True))
        current = rotate(current)
    return min(candidates, key=lambda item: (item[0].bits, item[1], item[2]))


def canonical(shape: CompactShape) -> CompactShape:
    return canonical_with_transform(shape)[0]


def crystal_generator(shape: CompactShape) -> CompactShape:
    """Generate crystal in every empty/pin cell strictly below shape height."""
    rows = _rows_from_shape(shape)
    if not rows:
        return shape
    generated: list[int] = []
    for row in rows:
        values = list(ROW_CELLS[row])
        for column, value in enumerate(values):
            if value in (EMPTY, PIN):
                values[column] = CRYSTAL
        generated.append(
            sum(value << (2 * column) for column, value in enumerate(values))
        )
    # The generated region is vertically solid up to the global height, hence
    # already stable.  No gravity call is part of the cpcp reference operation.
    return CompactShape(_bits_from_rows(generated, shape.cap), shape.cap)


def pin_push(shape: CompactShape) -> CompactShape:
    """Apply one Pin Pusher, including overflow shatter and gravity."""
    height = shape.height
    if height == 0:
        return shape

    pin_row = 0
    bottom = shape.row(0)
    for column in range(WIDTH):
        if ((bottom >> (2 * column)) & 3) != EMPTY:
            pin_row |= PIN << (2 * column)

    # Keep one overflow row so top crystal components can be shattered before
    # the cap truncation.  This is equivalent to cpcp's shifted-result seeding.
    oversized = CompactShape(
        (shape.bits << BITS_PER_LAYER) | pin_row,
        shape.cap + 1,
    )
    if height >= shape.cap:
        overflow_layer = shape.cap
        seeds = [
            (overflow_layer, column)
            for column in range(WIDTH)
            if oversized.cell(overflow_layer, column) == CRYSTAL
        ]
        oversized = shatter_crystals(oversized, seeds)

    truncated = CompactShape(oversized.bits & cap_mask(shape.cap), shape.cap)
    return apply_gravity(truncated)


def _select_columns(shape: CompactShape, column_mask: int) -> CompactShape:
    selected_rows: list[int] = []
    for row in _rows_from_shape(shape):
        selected = 0
        for column in range(WIDTH):
            if column_mask & (1 << column):
                selected |= ((row >> (2 * column)) & 3) << (2 * column)
        selected_rows.append(selected)
    return CompactShape(_bits_from_rows(selected_rows, shape.cap), shape.cap)


def _crossing_crystal_seeds(
    shape: CompactShape, axis: CutAxis
) -> tuple[tuple[int, int], ...]:
    pairs = ((1, 2), (3, 0)) if axis == CutAxis.VERTICAL else ((0, 1), (3, 2))
    seeds: list[tuple[int, int]] = []
    for layer, row in enumerate(_rows_from_shape(shape)):
        crystals = ROW_CRYSTAL[row]
        for first, second in pairs:
            if crystals & (1 << first) and crystals & (1 << second):
                seeds.extend(((layer, first), (layer, second)))
    return tuple(seeds)


def cut(
    shape: CompactShape, axis: CutAxis | int = CutAxis.VERTICAL
) -> tuple[CompactShape, CompactShape]:
    """Cut into two halves, shatter severed crystal components, then gravity.

    Vertical returns ``(east, west)``. Horizontal returns ``(north, south)``.
    """
    resolved = CutAxis(axis)
    shattered = shatter_crystals(shape, _crossing_crystal_seeds(shape, resolved))
    if resolved == CutAxis.VERTICAL:
        first_mask, second_mask = EAST_COLUMNS, WEST_COLUMNS
    else:
        first_mask, second_mask = NORTH_COLUMNS, SOUTH_COLUMNS
    first = apply_gravity(_select_columns(shattered, first_mask))
    second = apply_gravity(_select_columns(shattered, second_mask))
    return first, second


def simple_split(
    shape: CompactShape, axis: CutAxis | int = CutAxis.VERTICAL
) -> tuple[CompactShape, CompactShape]:
    """Pure column split without shatter or gravity, for structural analysis."""
    resolved = CutAxis(axis)
    if resolved == CutAxis.VERTICAL:
        return _select_columns(shape, EAST_COLUMNS), _select_columns(shape, WEST_COLUMNS)
    return _select_columns(shape, NORTH_COLUMNS), _select_columns(shape, SOUTH_COLUMNS)


def _merge_sides(
    first: CompactShape,
    second: CompactShape,
    first_mask: int,
    second_mask: int,
    *,
    cap: int,
) -> CompactShape:
    first = first.recapped(cap)
    second = second.recapped(cap)
    first_rows = _rows_from_shape(first)
    second_rows = _rows_from_shape(second)
    rows: list[int] = []
    for layer in range(max(len(first_rows), len(second_rows))):
        left = first_rows[layer] if layer < len(first_rows) else 0
        right = second_rows[layer] if layer < len(second_rows) else 0
        row = 0
        for column in range(WIDTH):
            if first_mask & (1 << column):
                value = (left >> (2 * column)) & 3
            elif second_mask & (1 << column):
                value = (right >> (2 * column)) & 3
            else:
                value = EMPTY
            row |= value << (2 * column)
        rows.append(row)
    return CompactShape(_bits_from_rows(rows, cap), cap)


def swap(
    first: CompactShape,
    second: CompactShape,
    axis: CutAxis | int = CutAxis.VERTICAL,
) -> tuple[CompactShape, CompactShape]:
    """Apply the Swapper and return its two outputs."""
    cap = max(first.cap, second.cap)
    first = first.recapped(cap)
    second = second.recapped(cap)
    resolved = CutAxis(axis)
    a0, a1 = cut(first, resolved)
    b0, b1 = cut(second, resolved)
    if resolved == CutAxis.VERTICAL:
        output0 = _merge_sides(a0, b1, EAST_COLUMNS, WEST_COLUMNS, cap=cap)
        output1 = _merge_sides(b0, a1, EAST_COLUMNS, WEST_COLUMNS, cap=cap)
    else:
        output0 = _merge_sides(a0, b1, NORTH_COLUMNS, SOUTH_COLUMNS, cap=cap)
        output1 = _merge_sides(b0, a1, NORTH_COLUMNS, SOUTH_COLUMNS, cap=cap)
    return output0, output1


def stack(bottom: CompactShape, top: CompactShape) -> CompactShape:
    """Stack using the authoritative high workspace with one empty gap row."""
    cap = max(bottom.cap, top.cap)
    bottom = bottom.recapped(cap)
    top = top.recapped(cap)
    workspace_cap = 2 * cap + 1
    workspace_bits = bottom.bits | (top.bits << (BITS_PER_LAYER * (cap + 1)))
    workspace = CompactShape(workspace_bits, workspace_cap)
    settled = apply_gravity(workspace)
    return CompactShape(settled.bits & cap_mask(cap), cap)


def stack_compact_equivalent(bottom: CompactShape, top: CompactShape) -> CompactShape:
    """Project-style optimized Stack, for differential/equivalence tests."""
    cap = max(bottom.cap, top.cap)
    bottom = bottom.recapped(cap)
    top = top.recapped(cap)
    top_rows = _rows_from_shape(top)
    cleaned_rows: list[int] = []
    for row in top_rows:
        cleaned = row
        crystal_mask = ROW_CRYSTAL[row]
        for column in range(WIDTH):
            if crystal_mask & (1 << column):
                cleaned &= ~(0b11 << (2 * column))
        cleaned_rows.append(cleaned)
    top_bits = _bits_from_rows(cleaned_rows, cap)
    shift_layers = bottom.height
    workspace_cap = max(cap, shift_layers + len(cleaned_rows))
    workspace = CompactShape(
        bottom.bits | (top_bits << (BITS_PER_LAYER * shift_layers)),
        workspace_cap,
    )
    settled = apply_gravity(workspace)
    return CompactShape(settled.bits & cap_mask(cap), cap)


def paint_structural(shape: CompactShape) -> CompactShape:
    """Painter is the identity on structural cell classes."""
    return shape


__all__ = [
    "CutAxis",
    "apply_gravity",
    "canonical",
    "canonical_with_transform",
    "crystal_component_positions",
    "crystal_generator",
    "cut",
    "dihedral_variants",
    "is_stable",
    "mirror",
    "occupied_positions",
    "paint_structural",
    "pin_push",
    "rotate",
    "shatter_crystals",
    "simple_split",
    "stack",
    "stack_compact_equivalent",
    "support_positions",
    "swap",
]
