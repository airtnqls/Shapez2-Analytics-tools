"""Small immutable structural physics oracle used only by corner-half research tests.

Cells are one of ``- S P c`` and rows are stored bottom-to-top.  The code is
kept independent of the legacy mutable Shape implementation so branch-local
proof obligations can be replayed before the core-kernel branch is merged.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

EMPTY, NORMAL, PIN, CRYSTAL = "-", "S", "P", "c"
ALPHABET = {EMPTY, NORMAL, PIN, CRYSTAL}
ADJ = ((1, 3), (0, 2), (1, 3), (0, 2))


def _trim(rows: list[list[str]]) -> list[list[str]]:
    while rows and all(x == EMPTY for x in rows[-1]):
        rows.pop()
    return rows


@dataclass(frozen=True)
class StructuralShape:
    rows: tuple[tuple[str, str, str, str], ...]
    cap: int

    def __post_init__(self) -> None:
        if self.cap < 0:
            raise ValueError("negative cap")
        for row in self.rows:
            if len(row) != 4 or any(x not in ALPHABET for x in row):
                raise ValueError(f"invalid row {row!r}")
        if len(self.rows) > self.cap:
            raise ValueError("shape exceeds cap")

    @classmethod
    def empty(cls, cap: int) -> "StructuralShape":
        return cls((), cap)

    @classmethod
    def from_code(cls, code: str, cap: int | None = None) -> "StructuralShape":
        raw = [] if not code else [list(part) for part in code.split(":")]
        for row in raw:
            if len(row) != 4:
                raise ValueError(f"row must have four cells: {row}")
        _trim(raw)
        final_cap = max(len(raw), cap or 0)
        return cls(tuple(tuple(row) for row in raw), final_cap)

    @classmethod
    def from_columns(cls, columns: Sequence[str], cap: int) -> "StructuralShape":
        if len(columns) != 4:
            raise ValueError("four columns required")
        rows: list[list[str]] = []
        for layer in range(cap):
            rows.append([
                columns[q][layer] if layer < len(columns[q]) else EMPTY
                for q in range(4)
            ])
        _trim(rows)
        return cls(tuple(tuple(row) for row in rows), cap)

    def code(self) -> str:
        return ":".join("".join(row) for row in self.rows)

    def cell(self, layer: int, q: int) -> str:
        if 0 <= layer < len(self.rows) and 0 <= q < 4:
            return self.rows[layer][q]
        return EMPTY

    def column(self, q: int) -> str:
        value = "".join(self.cell(layer, q) for layer in range(len(self.rows)))
        return value.rstrip(EMPTY)

    def height(self) -> int:
        return len(self.rows)

    def occupied(self, layer: int, q: int) -> bool:
        return self.cell(layer, q) != EMPTY

    def mutable(self, height: int | None = None) -> list[list[str]]:
        n = max(len(self.rows), height or 0)
        rows = [list(row) for row in self.rows]
        rows.extend([[EMPTY] * 4 for _ in range(n - len(rows))])
        return rows

    def rotate_cw(self) -> "StructuralShape":
        # old TL(3)->new TR(0), TR->BR, BR->BL, BL->TL
        rows = [[row[3], row[0], row[1], row[2]] for row in self.rows]
        return StructuralShape(tuple(tuple(r) for r in rows), self.cap)

    def rotate_180(self) -> "StructuralShape":
        return self.rotate_cw().rotate_cw()

    def mirror(self) -> "StructuralShape":
        # Reflect left/right: TR<->TL and BR<->BL.
        rows = [[row[3], row[2], row[1], row[0]] for row in self.rows]
        return StructuralShape(tuple(tuple(r) for r in rows), self.cap)


def _horizontal_group(rows: Sequence[Sequence[str]], layer: int, start_q: int) -> set[tuple[int, int]]:
    start = rows[layer][start_q]
    if start == EMPTY:
        return set()
    if start == PIN:
        return {(layer, start_q)}
    if start == CRYSTAL:
        raise ValueError("fall groups never contain crystals")
    group: set[tuple[int, int]] = set()
    todo = [start_q]
    while todo:
        q = todo.pop()
        if (layer, q) in group or rows[layer][q] != NORMAL:
            continue
        group.add((layer, q))
        for nq in ADJ[q]:
            if rows[layer][nq] == NORMAL and (layer, nq) not in group:
                todo.append(nq)
    return group


def support_set(shape: StructuralShape) -> frozenset[tuple[int, int]]:
    rows = shape.rows
    h = len(rows)
    supported: set[tuple[int, int]] = {
        (0, q) for q in range(4) if h and rows[0][q] != EMPTY
    }
    changed = True
    while changed:
        changed = False
        for layer in range(h):
            for q in range(4):
                part = rows[layer][q]
                pos = (layer, q)
                if part == EMPTY or pos in supported:
                    continue
                ok = False
                if layer > 0 and (layer - 1, q) in supported:
                    ok = True
                if not ok and part != PIN:
                    for nq in ADJ[q]:
                        npart = rows[layer][nq]
                        if npart not in (EMPTY, PIN) and (layer, nq) in supported:
                            ok = True
                            break
                if (
                    not ok
                    and part == CRYSTAL
                    and layer + 1 < h
                    and rows[layer + 1][q] == CRYSTAL
                    and (layer + 1, q) in supported
                ):
                    ok = True
                if ok:
                    supported.add(pos)
                    changed = True
    return frozenset(supported)


def crystal_component(shape: StructuralShape, seeds: Iterable[tuple[int, int]]) -> frozenset[tuple[int, int]]:
    reached: set[tuple[int, int]] = set()
    todo = deque()
    for pos in seeds:
        if shape.cell(*pos) == CRYSTAL:
            reached.add(pos)
            todo.append(pos)
    while todo:
        layer, q = todo.popleft()
        for nl, nq in ((layer - 1, q), (layer + 1, q)):
            if shape.cell(nl, nq) == CRYSTAL and (nl, nq) not in reached:
                reached.add((nl, nq))
                todo.append((nl, nq))
        for nq in ADJ[q]:
            pos = (layer, nq)
            if shape.cell(*pos) == CRYSTAL and pos not in reached:
                reached.add(pos)
                todo.append(pos)
    return frozenset(reached)


def remove_cells(shape: StructuralShape, cells: Iterable[tuple[int, int]]) -> StructuralShape:
    rows = shape.mutable()
    for layer, q in cells:
        if 0 <= layer < len(rows):
            rows[layer][q] = EMPTY
    _trim(rows)
    return StructuralShape(tuple(tuple(r) for r in rows), shape.cap)


def shatter(shape: StructuralShape, seeds: Iterable[tuple[int, int]]) -> StructuralShape:
    return remove_cells(shape, crystal_component(shape, seeds))


def apply_gravity(shape: StructuralShape) -> StructuralShape:
    rows = shape.mutable()
    if not rows:
        return shape
    snapshot = StructuralShape(tuple(tuple(r) for r in rows), shape.cap)
    supported = support_set(snapshot)

    # Unsupported crystals shatter in one step.
    for layer in range(len(rows)):
        for q in range(4):
            if rows[layer][q] == CRYSTAL and (layer, q) not in supported:
                rows[layer][q] = EMPTY
    _trim(rows)

    # Unsupported non-crystal parts fall, bottom-up, as per-layer groups.
    visited: set[tuple[int, int]] = set()
    layer = 0
    while layer < len(rows):
        for q in range(4):
            if (layer, q) in visited:
                continue
            part = rows[layer][q]
            if part in (EMPTY, CRYSTAL) or (layer, q) in supported:
                continue
            group = _horizontal_group(rows, layer, q)
            visited.update(group)
            if not group:
                continue
            distance = layer
            for gl, gq in group:
                free = 0
                check = gl - 1
                while check >= 0 and rows[check][gq] == EMPTY:
                    free += 1
                    check -= 1
                distance = min(distance, free)
            if distance:
                pieces = [(gl, gq, rows[gl][gq]) for gl, gq in group]
                for gl, gq, _ in pieces:
                    rows[gl][gq] = EMPTY
                for gl, gq, value in pieces:
                    rows[gl - distance][gq] = value
        layer += 1
    _trim(rows)
    return StructuralShape(tuple(tuple(r) for r in rows), shape.cap)


def is_stable(shape: StructuralShape) -> bool:
    return apply_gravity(shape) == shape


def pin_push(shape: StructuralShape) -> StructuralShape:
    cap = shape.cap
    old = shape.mutable(cap)
    workspace = [[EMPTY] * 4 for _ in range(cap + 1)]
    for q in range(4):
        if old and old[0][q] != EMPTY:
            workspace[0][q] = PIN
    for layer in range(cap):
        workspace[layer + 1] = list(old[layer])

    overflow = workspace[cap]
    overflow_crystals = {(cap, q) for q, part in enumerate(overflow) if part == CRYSTAL}
    oversized = StructuralShape(tuple(tuple(r) for r in workspace), cap + 1)
    destroyed = crystal_component(oversized, overflow_crystals)
    for layer, q in destroyed:
        workspace[layer][q] = EMPTY
    # The entire overflow layer is trimmed, including non-crystals and pins.
    workspace = workspace[:cap]
    _trim(workspace)
    return apply_gravity(StructuralShape(tuple(tuple(r) for r in workspace), cap))


def cut(shape: StructuralShape) -> tuple[StructuralShape, StructuralShape]:
    seeds: set[tuple[int, int]] = set()
    for layer in range(shape.height()):
        for a, b in ((0, 3), (1, 2)):
            if shape.cell(layer, a) == CRYSTAL and shape.cell(layer, b) == CRYSTAL:
                seeds.add((layer, a))
                seeds.add((layer, b))
    broken = shatter(shape, seeds)
    east_rows = []
    west_rows = []
    for row in broken.rows:
        east_rows.append([row[0], row[1], EMPTY, EMPTY])
        west_rows.append([EMPTY, EMPTY, row[2], row[3]])
    east = apply_gravity(StructuralShape(tuple(tuple(r) for r in east_rows), shape.cap))
    west = apply_gravity(StructuralShape(tuple(tuple(r) for r in west_rows), shape.cap))
    return east, west


def stack_layer(shape: StructuralShape, values: Sequence[str]) -> StructuralShape:
    if len(values) != 4:
        raise ValueError("four values required")
    covered = [q for q, value in enumerate(values) if value != EMPTY]
    if not covered:
        return shape
    heights = []
    for q in covered:
        h = 0
        for layer in range(shape.height()):
            if shape.cell(layer, q) != EMPTY:
                h = layer + 1
        heights.append(h)
    landing = max(heights)
    if landing >= shape.cap:
        return shape
    rows = shape.mutable(landing + 1)
    for q, value in enumerate(values):
        if value != EMPTY:
            rows[landing][q] = value
    _trim(rows)
    return StructuralShape(tuple(tuple(r) for r in rows), shape.cap)
