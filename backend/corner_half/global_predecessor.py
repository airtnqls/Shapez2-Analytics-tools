"""All-layer global predecessor compiler recovered from the legacy Corner tracer.

The legacy implementation did not construct an event Corner cell by cell.  It
read the complete target column once and synthesized four predecessor columns
whose *single* Pin Push performs all selected crystal shatters and ordinary-cell
falls at once.  This module is a typed, deterministic and replay-certified
version of that idea.

The compiler is a positive accelerator only.  Failure or a non-exact relation
never proves impossibility; callers must fall back to the complete Corner/Half
constructor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .corner_dfa import is_craftable_column, normalize_column
from .corner_regions import Route, analyze_column
from .structural_physics import EMPTY, code, column, is_stable, push_pin


class GlobalPredecessorError(ValueError):
    pass


class GlobalRelation(str, Enum):
    EXACT = "exact"
    BOTTOM_RECEIPT = "bottom_receipt"
    BOTTOM_ONLY_DIFFERENCE = "bottom_only_difference"
    OTHER = "other"


@dataclass(frozen=True)
class DropDuty:
    crystal_layer: int
    source: int
    target: int
    left_gap: int


@dataclass(frozen=True)
class GlobalPredecessorCertificate:
    target: str
    cap: int
    predecessor: str
    predecessor_columns: tuple[str, str, str, str]
    pushed: str
    pushed_columns: tuple[str, str, str, str]
    relation: GlobalRelation
    drops: tuple[DropDuty, ...]
    predecessor_stable: bool
    columns_craftable: tuple[bool, bool, bool, bool]
    column_routes: tuple[Route | None, Route | None, Route | None, Route | None]
    inspections: int
    replay_ok: bool

    @property
    def helpers_all_craftable(self) -> bool:
        return all(self.columns_craftable)

    @property
    def predecessor_is_natural(self) -> bool:
        return all(route is not Route.EVENT for route in self.column_routes)


class _PredecessorDSU:
    """Greatest still-nonempty predecessor with amortized O(alpha(L)) updates."""

    def __init__(self, cells: list[str]) -> None:
        self.parent = list(range(len(cells)))
        for index, cell in enumerate(cells):
            if cell == EMPTY:
                self.parent[index] = self.find(index - 1)

    def find(self, index: int) -> int:
        if index < 0:
            return -1
        parent = self.parent[index]
        if parent == index:
            return index
        self.parent[index] = self.find(parent)
        return self.parent[index]

    def remove(self, index: int) -> None:
        self.parent[index] = self.find(index - 1)


def _rightmost_crystal_cluster_left(target: str) -> int:
    index = len(target) - 1
    while index >= 0 and target[index] != "c":
        index -= 1
    if index < 0:
        return -1
    while index > 0 and target[index - 1] == "c":
        index -= 1
    return index - 1 if index > 0 else 0


def _relation(target: str, pushed_a: str) -> GlobalRelation:
    if pushed_a == target:
        return GlobalRelation.EXACT
    expected = (("P" if target and target[0] != EMPTY else EMPTY) + target[1:]).rstrip(EMPTY)
    if pushed_a == expected:
        return GlobalRelation.BOTTOM_RECEIPT
    if len(pushed_a) == len(target) and pushed_a[1:] == target[1:]:
        return GlobalRelation.BOTTOM_ONLY_DIFFERENCE
    return GlobalRelation.OTHER


def _route_or_none(value: str) -> Route | None:
    try:
        return analyze_column(value).route
    except ValueError:
        return None


@lru_cache(maxsize=200_000)
def compile_global_predecessor(column_value: str, cap: int | None = None) -> GlobalPredecessorCertificate:
    target = normalize_column(column_value)
    if not target or "c" not in target:
        raise GlobalPredecessorError("global predecessor requires a crystal event column")
    if not is_craftable_column(target):
        raise GlobalPredecessorError("target is outside the exact Corner language")
    witness = analyze_column(target)
    if witness.route is not Route.EVENT:
        raise GlobalPredecessorError("target is not on the event route")
    if cap is None:
        cap = len(target)
    if cap != len(target):
        # The recovered construction is a full-height overflow compiler.  A
        # shorter target can be embedded by its caller after choosing workspace
        # headroom, but silently padding here changes the legacy receipt logic.
        raise GlobalPredecessorError("global predecessor currently requires cap == target height")

    inspections = 0
    work = list(target)
    available_s: list[int] = []
    dsu = _PredecessorDSU(work)
    drops: list[DropDuty] = []

    # One left-to-right pass reproduces the legacy nearest-unconsumed-S rule.
    for index, cell in enumerate(target):
        inspections += 1
        if cell == "S":
            available_s.append(index)
            continue
        if cell != "c" or index == 0 or work[index - 1] != EMPTY:
            continue
        while available_s and work[available_s[-1]] != "S":
            available_s.pop()
        if not available_s:
            continue
        source = available_s.pop()
        predecessor = dsu.find(source - 1)
        gap = source - predecessor - 1
        if predecessor < 0:
            gap -= 1  # exact legacy floor convention
        target_layer = index - 1
        drops.append(DropDuty(index, source, target_layer, gap))
        work[source] = EMPTY
        dsu.remove(source)

    l2 = _rightmost_crystal_cluster_left(target)
    highest_c = target.rfind("c")

    a = work.copy()
    for index in range(highest_c + 1):
        inspections += 1
        if a[index] == EMPTY:
            a[index] = "c"
    for duty in drops:
        a[duty.target] = "S"
    a = a[1:] + [EMPTY]
    if target[0] in (EMPTY, "S"):
        for index, cell in enumerate(a):
            inspections += 1
            if cell != "c":
                break
            a[index] = EMPTY

    b = list(target)
    if l2 >= 0:
        for index in range(min(l2 + 1, cap)):
            inspections += 1
            if b[index] == EMPTY:
                b[index] = "P"
    for index, cell in enumerate(b):
        inspections += 1
        if cell == "c":
            b[index] = "S"
    for index in range(highest_c, cap):
        inspections += 1
        if b[index] == EMPTY:
            b[index] = "S"
    b = b[1:] + [EMPTY]

    relay = [EMPTY] * cap
    if l2 >= 0:
        for index in range(min(l2 + 1, cap)):
            relay[index] = "c"
    drop_sources = {duty.source for duty in drops}
    for index, cell in enumerate(target):
        inspections += 1
        if cell in ("c", "S") and index not in drop_sources and relay[index] == "c":
            relay[index] = "S"
    for duty in drops:
        relay[duty.target] = "S"
        for delta in range(1, duty.left_gap + 1):
            if duty.target - delta >= 0:
                relay[duty.target - delta] = "S"
    relay = relay[1:] + [EMPTY]

    overflow = ["c"] * cap
    if target[0] == "S":
        for index, cell in enumerate(a):
            inspections += 1
            if cell != EMPTY:
                break
            if index + 1 >= cap or a[index + 1] != EMPTY:
                a[index] = "S"
                if relay[index] == "S":
                    relay[index] = "c"
                    relay[0] = "S"
                break

    # Ring order A,B,C,D.  Legacy format_final_result wrote A,B,D,C, where its
    # local D was the all-crystal overflow column.
    rows = [[a[layer], b[layer], overflow[layer], relay[layer]] for layer in range(cap)]
    predecessor = code(rows)
    predecessor_columns = tuple(column(rows, q) for q in range(4))
    stable = is_stable(rows)
    pushed_rows = push_pin(rows, cap)
    pushed = code(pushed_rows)
    pushed_columns = tuple(column(pushed_rows, q) for q in range(4))
    relation = _relation(target, pushed_columns[0])
    craftable = tuple(is_craftable_column(value) for value in predecessor_columns)
    routes = tuple(_route_or_none(value) for value in predecessor_columns)
    replay_ok = stable and all(craftable) and relation is not GlobalRelation.OTHER
    return GlobalPredecessorCertificate(
        target=target,
        cap=cap,
        predecessor=predecessor,
        predecessor_columns=predecessor_columns,  # type: ignore[arg-type]
        pushed=pushed,
        pushed_columns=pushed_columns,  # type: ignore[arg-type]
        relation=relation,
        drops=tuple(drops),
        predecessor_stable=stable,
        columns_craftable=craftable,  # type: ignore[arg-type]
        column_routes=routes,  # type: ignore[arg-type]
        inspections=inspections,
        replay_ok=replay_ok,
    )


__all__ = [
    "DropDuty",
    "GlobalPredecessorCertificate",
    "GlobalPredecessorError",
    "GlobalRelation",
    "compile_global_predecessor",
]
