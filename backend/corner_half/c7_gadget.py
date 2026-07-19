"""Concrete structural compiler for the C7 overflow-event gadget.

This module tackles the remaining local lemma of the Corner lower bound.  It
compiles a *post-lift* target-column event snapshot and a separated list of
faller duties into a four-column predecessor for one Pin Pusher operation.

The result is a structural predecessor/certificate.  Its four helper columns
are lowered to raw-input child proofs by :mod:`proof_dag`; no synthetic helper
leaf remains in the completed constructor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .structural_physics import (
    CRYSTAL,
    EMPTY,
    ORDINARY,
    PIN,
    column,
    code,
    get,
    is_stable,
    trim,
    push_pin,
)


class DutyKind(str, Enum):
    ANCHORED = "anchored"
    NATURAL = "natural"
    FLOOR = "floor"


@dataclass(frozen=True, order=True)
class C7Duty:
    source: int
    target: int
    kind: DutyKind = DutyKind.ANCHORED


@dataclass(frozen=True)
class C7Certificate:
    cap: int
    post_lift_a: str
    duties: tuple[C7Duty, ...]
    anchors: tuple[int | None, ...]
    predecessor: str
    expected_a: str
    actual_a: str
    stable_predecessor: bool
    replay_ok: bool
    predecessor_columns: tuple[str, str, str, str]
    helper_columns_craftable: bool


class C7CompilationError(ValueError):
    pass


def _trim_string(s: str) -> str:
    return s.rstrip(EMPTY)


def _cell(s: str, i: int) -> str:
    return s[i] if 0 <= i < len(s) else EMPTY


def _crystal_runs_touching(a: str, intervals: Iterable[range]) -> set[int]:
    touched = set()
    path = {i for r in intervals for i in r}
    for i, ch in enumerate(a):
        if ch != CRYSTAL or i not in path:
            continue
        lo = i
        while lo > 0 and a[lo - 1] == CRYSTAL:
            lo -= 1
        hi = i
        while hi + 1 < len(a) and a[hi + 1] == CRYSTAL:
            hi += 1
        touched.update(range(lo, hi + 1))
    return touched


def _expected_after_event(post_lift_a: str, duties: Sequence[C7Duty]) -> str:
    a = list(post_lift_a)
    intervals = []
    for duty in duties:
        if duty.kind is DutyKind.FLOOR:
            intervals.append(range(0, duty.source))
        else:
            intervals.append(range(duty.target, duty.source))
    for i in _crystal_runs_touching(post_lift_a, intervals):
        a[i] = EMPTY
    # Faller groups are separated, so move bottom-up without interference.
    for duty in sorted(duties, key=lambda x: x.source):
        if a[duty.source] != ORDINARY:
            raise C7CompilationError(
                f"source {duty.source} is not an S after sacrificial shatter"
            )
        # The whole A-side fall path must be empty after the designated crystal
        # runs shatter.  Otherwise A itself blocks/supports the faller before
        # the D catcher can determine the requested landing.
        blocked = [
            layer
            for layer in range(duty.target, duty.source)
            if a[layer] != EMPTY
        ]
        if blocked:
            raise C7CompilationError(
                f"A fall path for {duty} is not empty after shatter: {blocked}"
            )
        a[duty.source] = EMPTY
        a[duty.target] = ORDINARY
    return _trim_string("".join(a))


def _validate_snapshot(post_a: str, cap: int, duties: Sequence[C7Duty]) -> None:
    if len(post_a) > cap:
        raise C7CompilationError("A must stay below the overflow layer")
    if not post_a:
        raise C7CompilationError("empty A snapshot")
    pre_a = post_a[1:]
    expected_receipt = PIN if pre_a and pre_a[0] != EMPTY else EMPTY
    if post_a[0] != expected_receipt:
        raise C7CompilationError(
            f"receipt mismatch: post A[0]={post_a[0]!r}, expected {expected_receipt!r}"
        )

    # At the event stage, pins below surviving crystals can only be the
    # bottom receipt/push run.  A floating or interrupted pin cannot be held by
    # B (pins neither give nor receive horizontal support) and would move in
    # the event gravity pass.
    seen_nonpin = False
    for layer, cell in enumerate(post_a):
        if cell == PIN and seen_nonpin:
            raise C7CompilationError(
                f"non-prefix A pin at layer {layer} is not a static C7 duty"
            )
        if cell != PIN:
            seen_nonpin = True

    last_source = -1
    floor_count = 0
    for duty in sorted(duties, key=lambda x: x.source):
        if not (0 <= duty.target < duty.source < cap):
            raise C7CompilationError(f"bad duty {duty}")
        if _cell(post_a, duty.source) != ORDINARY:
            raise C7CompilationError(f"duty source is not S: {duty}")
        if duty.source <= last_source:
            raise C7CompilationError("duty sources must be distinct")
        last_source = duty.source
        if duty.kind is DutyKind.FLOOR:
            floor_count += 1
            if duty.target != 0 or post_a[0] != EMPTY:
                raise C7CompilationError("floor duty requires empty A receipt at target 0")
        elif duty.target == 0:
            raise C7CompilationError("target 0 must use FLOOR duty")
    if floor_count > 1:
        raise C7CompilationError("at most one floor duty")
    if floor_count and min(duties, key=lambda x: x.source).kind is not DutyKind.FLOOR:
        raise C7CompilationError("floor duty must be the lowest duty")


def _find_anchor(
    post_a: str,
    lower_source: int,
    target: int,
    destroyed_a: set[int],
    faller_sources: set[int],
) -> int:
    # The D anchor must be supported by an A cell that survives this same
    # overflow event.  Merely being occupied before shattering is insufficient
    # when a crystal is fused to a relay-touched sacrificial run.
    for layer in range(target - 2, lower_source, -1):
        if (
            _cell(post_a, layer) != EMPTY
            and layer not in destroyed_a
            and layer not in faller_sources
        ):
            return layer
    raise C7CompilationError(
        "no surviving static A anchor strictly between "
        f"lower source {lower_source} and target {target}"
    )


def compile_c7(post_lift_a: str, cap: int, duties: Sequence[C7Duty]) -> C7Certificate:
    """Compile and replay one concrete C7 predecessor.

    ``post_lift_a`` uses coordinates *after* the Pin Pusher lift and receipt,
    but before overflow shattering/gravity.  This matches the coordinate
    convention in the C7 statement.
    """

    post_a = _trim_string(post_lift_a)
    duties = tuple(sorted(duties, key=lambda x: x.source))
    _validate_snapshot(post_a, cap, duties)
    intervals = [
        range(0, d.source) if d.kind is DutyKind.FLOOR
        else range(d.target, d.source)
        for d in duties
    ]
    destroyed_a = _crystal_runs_touching(post_a, intervals)
    for duty in duties:
        if duty.kind is DutyKind.ANCHORED:
            below = duty.target - 1
            if _cell(post_a, below) != EMPTY and below not in destroyed_a:
                raise C7CompilationError(
                    f"anchored duty leaves A occupied below target after shatter: {duty}"
                )
        elif duty.kind is DutyKind.NATURAL:
            below = duty.target - 1
            if _cell(post_a, below) == EMPTY or below in destroyed_a:
                raise C7CompilationError(
                    f"natural duty lacks a surviving A blocker below target: {duty}"
                )
    expected_a = _expected_after_event(post_a, duties)
    faller_sources = {d.source for d in duties}

    max_a = max((i for i, ch in enumerate(post_a) if ch != EMPTY), default=0)
    top = max(max_a, max((d.source for d in duties), default=0))

    # Post-lift helper columns.  C has its overflow crystal at layer cap.
    post_b = [EMPTY] * (cap + 1)
    post_c = [EMPTY] * (cap + 1)
    post_d = [EMPTY] * (cap + 1)

    post_c[0] = PIN
    for l in range(1, cap + 1):
        post_c[l] = CRYSTAL

    # Continuous static-side tower: every level is occupied, with a pin beside
    # each faller and an S everywhere else.  This closes the support-gap issue
    # identified by the proof audit.
    post_b[0] = PIN
    faller_layers = {d.source for d in duties}
    for l in range(1, top + 1):
        post_b[l] = PIN if l in faller_layers else ORDINARY

    anchors: list[int | None] = []
    lower_source = -1
    have_grounded_unit = False
    for index, duty in enumerate(duties):
        f, t = duty.source, duty.target
        if duty.kind is DutyKind.FLOOR:
            # The D receipt pin at 0 supports the relay chain.  The source-level
            # relay is the faller's pre-event horizontal support.  A harmless
            # S cap at f+1 sits beside the zone's lowest keeper; it remains
            # supported after the relays die and makes D's next crystal-free
            # segment start with S, so the helper column is itself craftable.
            if f + 1 >= cap or _cell(post_a, f + 1) == EMPTY:
                raise C7CompilationError(
                    "floor duty requires the static lowest keeper at source+1"
                )
            post_d[0] = PIN
            for l in range(1, f + 1):
                if post_d[l] != EMPTY:
                    raise C7CompilationError("overlapping floor D unit")
                post_d[l] = CRYSTAL
            if post_d[f + 1] != EMPTY:
                raise C7CompilationError("floor D cap overlaps another unit")
            post_d[f + 1] = ORDINARY
            anchors.append(None)
            have_grounded_unit = True
            # The S cap at f+1 may be reused as the anchor of the first
            # upper unit.  Keep the separation boundary at the faller source.
            lower_source = f
            continue

        if not have_grounded_unit:
            anchor = None
            post_d[0] = PIN
            pin_start = 1
            have_grounded_unit = True
        else:
            anchor = _find_anchor(
                post_a, lower_source, t, destroyed_a, faller_sources
            )
            if post_d[anchor] not in (EMPTY, ORDINARY):
                raise C7CompilationError("D anchor overlaps a lower unit")
            post_d[anchor] = ORDINARY
            pin_start = anchor + 1
        anchors.append(anchor)

        for l in range(pin_start, t):
            if post_d[l] != EMPTY:
                raise C7CompilationError("D pedestal overlaps another unit")
            post_d[l] = ORDINARY
        for l in range(t, f):
            if post_d[l] != EMPTY:
                raise C7CompilationError("D relay overlaps another unit")
            post_d[l] = CRYSTAL

        # NATURAL duties use the same rider/catcher as anchored duties.
        # The surviving A blocker and the D catcher are at the same height,
        # so the pair still lands at the natural target; keeping the rider
        # also makes the D helper's crystal run end in S.

        if post_d[f] != EMPTY:
            raise C7CompilationError("D rider overlaps another unit")
        post_d[f] = ORDINARY
        lower_source = f

    # Canonical support completion for D.  Fill every still-empty level up to
    # the active top with S.  D is then a grounded continuous tower (with its
    # relay c-runs and riders embedded), so the half {A,D} is independently
    # stable during the final helper exchange.  The added S cells are harmless:
    # at occupied A layers they duplicate static support; at empty A layers
    # they are not horizontally connected to A, and after relay shattering
    # they either remain supported from A/B or fall only inside D.
    for l in range(1, top + 1):
        if post_d[l] == EMPTY:
            post_d[l] = ORDINARY

    # A/C/B/D post-lift rows -> actual pre-push rows by removing receipt row.
    # Ring order is A-B-C-D.
    pre_rows = [[EMPTY] * 4 for _ in range(cap)]
    for l in range(cap):
        pre_rows[l][0] = _cell(post_a, l + 1)
        pre_rows[l][1] = post_b[l + 1]
        pre_rows[l][2] = post_c[l + 1]
        pre_rows[l][3] = post_d[l + 1]
    pre_rows = trim(pre_rows)
    stable = is_stable(pre_rows)
    out = push_pin(pre_rows, cap)
    actual_a = column(out, 0)
    from .corner_dfa import is_craftable_column

    pred_columns = tuple(column(pre_rows, q) for q in range(4))
    helpers_ok = all(is_craftable_column(pred_columns[q]) for q in (1, 2, 3))
    ok = stable and actual_a == expected_a and helpers_ok
    return C7Certificate(
        cap=cap,
        post_lift_a=post_a,
        duties=duties,
        anchors=tuple(anchors),
        predecessor=code(pre_rows),
        expected_a=expected_a,
        actual_a=actual_a,
        stable_predecessor=stable,
        replay_ok=ok,
        predecessor_columns=pred_columns,
        helper_columns_craftable=helpers_ok,
    )
