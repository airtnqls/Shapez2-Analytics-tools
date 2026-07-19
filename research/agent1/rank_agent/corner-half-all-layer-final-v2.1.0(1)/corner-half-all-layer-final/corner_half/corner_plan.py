"""Abstract C1..C7 constructor schedule.

Human-readable summary of the exact constructor certificate.

The concrete four-column C7 compiler now lives in :mod:`c7_gadget`; event
coordinates below are taken from :func:`compile_corner_event`, not from the
older region-relative heuristic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .corner_regions import CornerWitness, Route, analyze_column


class CRule(str, Enum):
    C1_DEPOSIT = "C1"
    C2_ANCHORED_DEPOSIT = "C2"
    C3_GENERATE = "C3"
    C4_SHATTER = "C4"
    C5_DESCEND = "C5"
    C6_PUSH = "C6"
    C7_EVENT = "C7"


@dataclass(frozen=True)
class EventDuty:
    region: str
    source: int
    target: int


@dataclass(frozen=True)
class PlanStep:
    rule: CRule
    detail: str
    layer: int | None = None


@dataclass(frozen=True)
class AbstractCornerPlan:
    target: str
    route: Route
    steps: tuple[PlanStep, ...]
    event_duties: tuple[EventDuty, ...] = ()
    requires_c7_compiler: bool = False


def compile_abstract(column: str) -> AbstractCornerPlan:
    witness = analyze_column(column)
    w = witness.regions
    steps: list[PlanStep] = []
    duties: list[EventDuty] = []

    if witness.route is Route.CRYSTAL_FREE:
        for layer, ch in enumerate(w.column):
            if ch in "SP":
                rule = CRule.C1_DEPOSIT if layer == 0 or w.column[layer - 1] != "-" else CRule.C2_ANCHORED_DEPOSIT
                steps.append(PlanStep(rule, f"deposit {ch}", layer))
        return AbstractCornerPlan(w.column, witness.route, tuple(steps))

    # Skeleton: all final S cells below the topmost crystal are conservative
    # holder positions; sacrificial crystal runs are inserted by C3 and later
    # removed by C4/C7.  A concrete witness compiler may remove redundant S's.
    top_crystal = w.crystal_positions[-1]
    for layer, ch in enumerate(w.column[: top_crystal + 1]):
        if ch == "S":
            below = layer > 0 and w.column[layer - 1] != "-"
            steps.append(PlanStep(CRule.C1_DEPOSIT if layer == 0 or below else CRule.C2_ANCHORED_DEPOSIT, "snapshot S", layer))
    steps.append(PlanStep(CRule.C3_GENERATE, "single last generation", top_crystal + 1))

    if witness.route is Route.EVENT:
        from .corner_event_plan import compile_corner_event
        exact = compile_corner_event(w.column, max(1, len(w.column)))
        duties.extend(
            EventDuty(f"duty[{i}]", duty.source, duty.target)
            for i, duty in enumerate(exact.duties)
        )
        steps.append(PlanStep(CRule.C7_EVENT, f"overflow event with {len(duties)} fallers"))

    # The final top region is always deposited after all kept crystals.
    for rel, ch in enumerate(w.top):
        if ch in "SP":
            layer = top_crystal + 1 + rel
            rule = CRule.C1_DEPOSIT if rel == 0 or w.top[rel - 1] != "-" else CRule.C2_ANCHORED_DEPOSIT
            steps.append(PlanStep(rule, f"top {ch}", layer))

    return AbstractCornerPlan(
        w.column,
        witness.route,
        tuple(steps),
        tuple(duties),
        requires_c7_compiler=(witness.route is Route.EVENT),
    )
