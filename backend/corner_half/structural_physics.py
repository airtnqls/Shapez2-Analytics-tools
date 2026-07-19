"""Small exact structural Shapez 2 physics kernel for branch proofs.

Cells are ``-`` (empty), ``S`` (ordinary), ``P`` (pin), ``c`` (crystal).
Rows are bottom-to-top and have four columns in ring order A,B,C,D.
This module is intentionally independent of the legacy mutable Shape class.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Iterator, Sequence

EMPTY = "-"
ORDINARY = "S"
PIN = "P"
CRYSTAL = "c"
VALID = {EMPTY, ORDINARY, PIN, CRYSTAL}
ADJ = ((1, 3), (0, 2), (1, 3), (0, 2))
Coord = tuple[int, int]


def _norm_rows(rows: Sequence[Sequence[str]], height: int | None = None) -> list[list[str]]:
    out = [list(row) for row in rows]
    for row in out:
        if len(row) != 4 or any(cell not in VALID for cell in row):
            raise ValueError(f"invalid structural row: {row!r}")
    if height is not None:
        if len(out) > height:
            out = out[:height]
        while len(out) < height:
            out.append([EMPTY] * 4)
    return out


def trim(rows: Sequence[Sequence[str]]) -> list[list[str]]:
    out = _norm_rows(rows)
    while out and all(cell == EMPTY for cell in out[-1]):
        out.pop()
    return out


def code(rows: Sequence[Sequence[str]]) -> str:
    return ":".join("".join(row) for row in trim(rows))


def parse(value: str, height: int | None = None) -> list[list[str]]:
    rows = [] if not value else [list(part) for part in value.split(":")]
    return _norm_rows(rows, height)


def get(rows: Sequence[Sequence[str]], layer: int, column: int) -> str:
    if 0 <= layer < len(rows) and 0 <= column < 4:
        return rows[layer][column]
    return EMPTY


def occupied(cell: str) -> bool:
    return cell != EMPTY


def nonpin(cell: str) -> bool:
    return cell in (ORDINARY, CRYSTAL)


def crystal_component(rows: Sequence[Sequence[str]], seeds: Iterable[Coord]) -> set[Coord]:
    h = len(rows)
    todo = deque()
    seen: set[Coord] = set()
    for pos in seeds:
        l, q = pos
        if get(rows, l, q) == CRYSTAL:
            todo.append(pos)
            seen.add(pos)
    while todo:
        l, q = todo.popleft()
        for nq in ADJ[q]:
            nxt = (l, nq)
            if nxt not in seen and get(rows, *nxt) == CRYSTAL:
                seen.add(nxt)
                todo.append(nxt)
        for nl in (l - 1, l + 1):
            nxt = (nl, q)
            if 0 <= nl < h and nxt not in seen and get(rows, *nxt) == CRYSTAL:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def support_closure(rows: Sequence[Sequence[str]]) -> set[Coord]:
    """Least support fixed point, computed as a directed reachability BFS.

    Each inference rule is an outgoing edge from an already-supported cell:
    vertical-up to any occupied cell, horizontal to adjacent non-pins, and
    crystal-hanging downward to a crystal.  Thus a queue computes exactly the
    same least fixed point in O(number of cells).
    """
    h = len(rows)
    supported: set[Coord] = set()
    todo: deque[Coord] = deque()

    if h:
        for q in range(4):
            if occupied(rows[0][q]):
                pos=(0,q)
                supported.add(pos)
                todo.append(pos)

    def add(pos: Coord) -> None:
        if pos not in supported:
            supported.add(pos)
            todo.append(pos)

    while todo:
        l,q=todo.popleft()
        cell=rows[l][q]
        if l+1<h and occupied(rows[l+1][q]):
            add((l+1,q))
        if nonpin(cell):
            for nq in ADJ[q]:
                if nonpin(rows[l][nq]):
                    add((l,nq))
        if cell==CRYSTAL and l>0 and rows[l-1][q]==CRYSTAL:
            add((l-1,q))
    return supported


def _ordinary_group_at_layer(
    rows: Sequence[Sequence[str]], layer: int, start_q: int, allowed: set[Coord]
) -> set[Coord]:
    if (layer, start_q) not in allowed:
        return set()
    if get(rows, layer, start_q) == PIN:
        return {(layer, start_q)}
    group: set[Coord] = set()
    todo = [start_q]
    while todo:
        q = todo.pop()
        pos = (layer, q)
        if pos in group or pos not in allowed or get(rows, layer, q) != ORDINARY:
            continue
        group.add(pos)
        for nq in ADJ[q]:
            if (layer, nq) in allowed and get(rows, layer, nq) == ORDINARY:
                todo.append(nq)
    return group


def apply_gravity(rows: Sequence[Sequence[str]]) -> list[list[str]]:
    """Reference one-pass gravity in O(L) time at fixed width four.

    Lower source layers settle first.  Therefore, immediately before source
    layer ``l`` is processed, ``highest_below[q]`` is the highest final
    occupied cell below ``l`` in column ``q``.  A group's free distance in that
    column is exactly ``l - highest_below[q] - 1``; no downward scan is needed.
    """
    work = _norm_rows(rows)
    h = len(work)
    supported = support_closure(work)

    unsupported_crystals = {
        (l, q)
        for l in range(h)
        for q in range(4)
        if work[l][q] == CRYSTAL and (l, q) not in supported
    }
    shattered = crystal_component(work, unsupported_crystals)
    for l, q in shattered:
        work[l][q] = EMPTY

    unsupported_noncrystal = {
        (l, q)
        for l in range(h)
        for q in range(4)
        if work[l][q] in (ORDINARY, PIN) and (l, q) not in supported
    }

    consumed: set[Coord] = set()
    highest_below = [-1, -1, -1, -1]
    for source_layer in range(h):
        for start_q in range(4):
            start = (source_layer, start_q)
            if start not in unsupported_noncrystal or start in consumed:
                continue
            group = _ordinary_group_at_layer(
                work, source_layer, start_q, unsupported_noncrystal - consumed
            )
            if not group:
                continue
            consumed.update(group)
            pieces = [(l, q, work[l][q]) for l, q in group]
            for l, q, _ in pieces:
                work[l][q] = EMPTY

            drop = min(
                source_layer - highest_below[q] - 1
                for _, q, _ in pieces
            )
            for l, q, cell in pieces:
                target = l - drop
                work[target][q] = cell
                if target > highest_below[q]:
                    highest_below[q] = target

        # Supported cells and zero-drop groups remaining at this source layer
        # become blockers for every later source layer.
        for q in range(4):
            if work[source_layer][q] != EMPTY:
                highest_below[q] = source_layer

    return trim(work)


def is_stable_by_replay(rows: Sequence[Sequence[str]]) -> bool:
    """Slow reference definition used by differential tests."""
    return code(rows) == code(apply_gravity(rows))


def is_stable(rows: Sequence[Sequence[str]]) -> bool:
    """Exact O(L) stability predicate.

    A shape is unchanged by a gravity pass iff every occupied cell is already
    in the least support fixed point.  The forward direction is immediate:
    an unsupported crystal is shattered, while the bottommost unsupported
    non-crystal group has positive free distance after all lower unsupported
    groups have settled, so it moves.  The reverse direction is immediate
    because support/shatter/fall then have no work to perform.
    """
    work = _norm_rows(rows)
    occupied_count = sum(cell != EMPTY for row in work for cell in row)
    return len(support_closure(work)) == occupied_count


def push_pin(rows: Sequence[Sequence[str]], cap: int) -> list[list[str]]:
    """Pin Pusher with overflow shatter and final gravity."""
    old = _norm_rows(rows, cap)
    shifted = [[EMPTY] * 4 for _ in range(cap + 1)]
    for q in range(4):
        if occupied(old[0][q]):
            shifted[0][q] = PIN
    for l in range(cap):
        shifted[l + 1] = old[l].copy()

    overflow_crystals = {
        (cap, q) for q in range(4) if shifted[cap][q] == CRYSTAL
    }
    shattered = crystal_component(shifted, overflow_crystals)
    for l, q in shattered:
        shifted[l][q] = EMPTY
    shifted.pop()  # every non-crystal overflow cell is truncated outright
    return apply_gravity(shifted)


@dataclass(frozen=True)
class StructuralShape:
    rows: tuple[tuple[str, str, str, str], ...]
    cap: int

    @classmethod
    def from_rows(cls, rows: Sequence[Sequence[str]], cap: int) -> "StructuralShape":
        normalized = _norm_rows(rows, cap)
        return cls(tuple(tuple(row) for row in normalized), cap)

    @classmethod
    def from_code(cls, value: str, cap: int) -> "StructuralShape":
        return cls.from_rows(parse(value, cap), cap)

    def to_rows(self) -> list[list[str]]:
        return [list(row) for row in self.rows]

    def code(self) -> str:
        return code(self.rows)

    def stable(self) -> bool:
        return is_stable(self.rows)

    def push_pin(self) -> "StructuralShape":
        return StructuralShape.from_rows(push_pin(self.rows, self.cap), self.cap)

# Compatibility names used by proof modules.
NORMAL = ORDINARY
normalize_rows = trim
encode = code


def column(rows: Sequence[Sequence[str]], q: int) -> str:
    chars = [get(rows, l, q) for l in range(len(rows))]
    while chars and chars[-1] == EMPTY:
        chars.pop()
    return "".join(chars)
