"""Deliberately simple list-based reference implementation.

This module mirrors the authoritative C++ algorithms closely and is kept
independent from the packed kernel.  It is intentionally slower and exists for
differential testing, proof auditing, and future refactors.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable, Sequence

from .model import CRYSTAL, EMPTY, NORMAL, PIN, WIDTH, CompactShape
from .tables import ADJACENT

Rows = list[list[int]]


def decode(shape: CompactShape, *, cap: int | None = None) -> Rows:
    resolved = shape.cap if cap is None else cap
    return [[shape.cell(layer, column) for column in range(WIDTH)] for layer in range(resolved)]


def encode(rows: Sequence[Sequence[int]], cap: int) -> CompactShape:
    return CompactShape.from_rows(rows[:cap], cap=cap)


def height(rows: Sequence[Sequence[int]]) -> int:
    for layer in range(len(rows) - 1, -1, -1):
        if any(rows[layer][column] != EMPTY for column in range(WIDTH)):
            return layer + 1
    return 0



def support_rows(source: Sequence[Sequence[int]]) -> list[list[bool]]:
    rows = [list(row) for row in source]
    nl = height(rows)
    supported = [[False] * WIDTH for _ in rows]
    if nl == 0:
        return supported
    for column in range(WIDTH):
        supported[0][column] = rows[0][column] != EMPTY
    changed = True
    while changed:
        changed = False
        for layer in range(nl):
            for column in range(WIDTH):
                if rows[layer][column] == EMPTY or supported[layer][column]:
                    continue
                if layer > 0 and supported[layer - 1][column]:
                    supported[layer][column] = True
                    changed = True
                    continue
                if rows[layer][column] != PIN:
                    for neighbor in ADJACENT[column]:
                        if supported[layer][neighbor] and rows[layer][neighbor] != PIN:
                            supported[layer][column] = True
                            changed = True
                            break
                    if supported[layer][column]:
                        continue
                if (
                    rows[layer][column] == CRYSTAL
                    and layer + 1 < nl
                    and supported[layer + 1][column]
                    and rows[layer + 1][column] == CRYSTAL
                ):
                    supported[layer][column] = True
                    changed = True
    return supported


def support_positions(shape: CompactShape) -> int:
    result = 0
    for layer, row in enumerate(support_rows(decode(shape))):
        for column, value in enumerate(row):
            if value:
                result |= 1 << (WIDTH * layer + column)
    return result

def apply_gravity_rows(source: Sequence[Sequence[int]]) -> Rows:
    rows = [list(row) for row in source]
    nl = height(rows)
    if nl == 0:
        return rows

    supported = support_rows(rows)

    for layer in range(nl):
        for column in range(WIDTH):
            if not supported[layer][column] and rows[layer][column] == CRYSTAL:
                rows[layer][column] = EMPTY

    dropped = [[False] * WIDTH for _ in rows]
    for layer in range(1, nl):
        for column in range(WIDTH):
            if (
                rows[layer][column] == EMPTY
                or supported[layer][column]
                or dropped[layer][column]
            ):
                continue

            group = [column]
            dropped[layer][column] = True
            if rows[layer][column] != PIN:
                cursor = 0
                while cursor < len(group):
                    current = group[cursor]
                    cursor += 1
                    for neighbor in ADJACENT[current]:
                        if (
                            not dropped[layer][neighbor]
                            and rows[layer][neighbor] != EMPTY
                            and not supported[layer][neighbor]
                            and rows[layer][neighbor] != PIN
                        ):
                            dropped[layer][neighbor] = True
                            group.append(neighbor)

            min_drop = layer
            for group_column in group:
                drop = layer
                for below in range(layer - 1, -1, -1):
                    if rows[below][group_column] != EMPTY:
                        drop = layer - below - 1
                        break
                min_drop = min(min_drop, drop)

            if min_drop > 0:
                for group_column in group:
                    rows[layer - min_drop][group_column] = rows[layer][group_column]
                    rows[layer][group_column] = EMPTY

    return rows


def apply_gravity(shape: CompactShape) -> CompactShape:
    return encode(apply_gravity_rows(decode(shape)), shape.cap)


def is_stable(shape: CompactShape) -> bool:
    return apply_gravity(shape) == shape


def shatter_rows(rows: Rows, seeds: Iterable[tuple[int, int]]) -> None:
    nl = height(rows)
    queue: deque[tuple[int, int]] = deque()
    seen: set[tuple[int, int]] = set()
    for layer, column in seeds:
        if (
            0 <= layer < nl
            and 0 <= column < WIDTH
            and rows[layer][column] == CRYSTAL
            and (layer, column) not in seen
        ):
            seen.add((layer, column))
            queue.append((layer, column))
    while queue:
        layer, column = queue.popleft()
        for neighbor in ADJACENT[column]:
            candidate = (layer, neighbor)
            if rows[layer][neighbor] == CRYSTAL and candidate not in seen:
                seen.add(candidate)
                queue.append(candidate)
        for next_layer in (layer - 1, layer + 1):
            candidate = (next_layer, column)
            if (
                0 <= next_layer < nl
                and rows[next_layer][column] == CRYSTAL
                and candidate not in seen
            ):
                seen.add(candidate)
                queue.append(candidate)
    for layer, column in seen:
        rows[layer][column] = EMPTY


def rotate(shape: CompactShape, turns: int = 1) -> CompactShape:
    turns %= WIDTH
    rows = decode(shape)
    for _ in range(turns):
        rows = [[row[3], row[0], row[1], row[2]] for row in rows]
    return encode(rows, shape.cap)


def mirror(shape: CompactShape) -> CompactShape:
    return encode([list(reversed(row)) for row in decode(shape)], shape.cap)


def crystal_generator(shape: CompactShape) -> CompactShape:
    rows = decode(shape)
    for layer in range(height(rows)):
        for column in range(WIDTH):
            if rows[layer][column] in (EMPTY, PIN):
                rows[layer][column] = CRYSTAL
    return encode(rows, shape.cap)


def pin_push(shape: CompactShape) -> CompactShape:
    rows = decode(shape)
    nl = height(rows)
    result = [[EMPTY] * WIDTH for _ in rows]
    copy_count = min(nl, shape.cap - 1)
    for layer in range(copy_count):
        result[layer + 1] = rows[layer].copy()
    if nl > 0:
        for column in range(WIDTH):
            if rows[0][column] != EMPTY:
                result[0][column] = PIN
    if nl >= shape.cap:
        seeds = [
            (shape.cap - 1, column)
            for column in range(WIDTH)
            if rows[shape.cap - 1][column] == CRYSTAL
        ]
        shatter_rows(result, seeds)
    return encode(apply_gravity_rows(result), shape.cap)


def _cut_masks(axis: int) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    if axis == 0:
        return 0b0011, 0b1100, ((1, 2), (3, 0))
    if axis == 1:
        return 0b1001, 0b0110, ((0, 1), (3, 2))
    raise ValueError(axis)


def cut(shape: CompactShape, axis: int = 0) -> tuple[CompactShape, CompactShape]:
    rows = decode(shape)
    first_mask, second_mask, pairs = _cut_masks(axis)
    seeds: list[tuple[int, int]] = []
    for layer in range(height(rows)):
        for first, second in pairs:
            if rows[layer][first] == CRYSTAL and rows[layer][second] == CRYSTAL:
                seeds.extend(((layer, first), (layer, second)))

    def side(mask: int) -> CompactShape:
        copy = [row.copy() for row in rows]
        shatter_rows(copy, seeds)
        for layer in range(len(copy)):
            for column in range(WIDTH):
                if not mask & (1 << column):
                    copy[layer][column] = EMPTY
        return encode(apply_gravity_rows(copy), shape.cap)

    return side(first_mask), side(second_mask)


def _merge(
    first: CompactShape,
    second: CompactShape,
    first_mask: int,
    second_mask: int,
    cap: int,
) -> CompactShape:
    first_rows = decode(first.recapped(cap), cap=cap)
    second_rows = decode(second.recapped(cap), cap=cap)
    rows = [[EMPTY] * WIDTH for _ in range(cap)]
    for layer in range(cap):
        for column in range(WIDTH):
            if first_mask & (1 << column):
                rows[layer][column] = first_rows[layer][column]
            elif second_mask & (1 << column):
                rows[layer][column] = second_rows[layer][column]
    return encode(rows, cap)


def swap(
    first: CompactShape, second: CompactShape, axis: int = 0
) -> tuple[CompactShape, CompactShape]:
    cap = max(first.cap, second.cap)
    first = first.recapped(cap)
    second = second.recapped(cap)
    a0, a1 = cut(first, axis)
    b0, b1 = cut(second, axis)
    first_mask, second_mask, _ = _cut_masks(axis)
    return (
        _merge(a0, b1, first_mask, second_mask, cap),
        _merge(b0, a1, first_mask, second_mask, cap),
    )


def stack(bottom: CompactShape, top: CompactShape) -> CompactShape:
    cap = max(bottom.cap, top.cap)
    bottom_rows = decode(bottom.recapped(cap), cap=cap)
    top_rows = decode(top.recapped(cap), cap=cap)
    workspace = [[EMPTY] * WIDTH for _ in range(2 * cap + 1)]
    for layer in range(cap):
        workspace[layer] = bottom_rows[layer].copy()
        workspace[cap + 1 + layer] = top_rows[layer].copy()
    settled = apply_gravity_rows(workspace)
    return encode(settled[:cap], cap)
