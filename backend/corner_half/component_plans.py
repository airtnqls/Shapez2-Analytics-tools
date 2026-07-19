"""Exact component witnesses from the Corner lower-bound proof.

This module is deliberately one-dimensional.  It lowers the semantic cases in
§6.3 to explicit snapshot strings and C4/C5 move lists, then replays them in
the region move system used by the proof.  Absolute four-column operation
compilation lives one layer above this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .corner_regions import is_i_nat, is_i_weak


class RegionKind(str, Enum):
    SEGMENT = "segment"
    ZONE = "zone"


class MoveKind(str, Enum):
    SHATTER = "shatter"
    DESCEND = "descend"


@dataclass(frozen=True)
class RegionMove:
    kind: MoveKind
    layer: int


@dataclass(frozen=True)
class RegionPlan:
    kind: RegionKind
    target: str
    snapshot: str
    moves: tuple[RegionMove, ...]
    event_source: int | None = None
    event_target: int | None = None
    post_moves: tuple[RegionMove, ...] = ()


class RegionPlanError(ValueError):
    pass


def _runs(s: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(s):
        if s[i] != "c":
            i += 1
            continue
        j = i + 1
        while j < len(s) and s[j] == "c":
            j += 1
        out.append((i, j))
        i = j
    return out


def _shatter(state: list[str], layer: int) -> None:
    if not (0 <= layer < len(state)) or state[layer] != "c":
        raise RegionPlanError(f"no crystal run at {layer}: {''.join(state)}")
    lo = layer
    while lo > 0 and state[lo - 1] == "c":
        lo -= 1
    hi = layer + 1
    while hi < len(state) and state[hi] == "c":
        hi += 1
    for i in range(lo, hi):
        state[i] = "-"


def _descend(state: list[str], source: int) -> int:
    if not (0 <= source < len(state)) or state[source] != "S":
        raise RegionPlanError(f"no S at descent source {source}: {''.join(state)}")
    target = 0
    for i in range(source - 1, -1, -1):
        if state[i] != "-":
            target = i + 1
            break
    if target >= source:
        raise RegionPlanError(f"S at {source} cannot descend: {''.join(state)}")
    state[source] = "-"
    if state[target] != "-":
        raise RegionPlanError(f"descent target {target} occupied: {''.join(state)}")
    state[target] = "S"
    return target


def replay_region(plan: RegionPlan, *, include_event: bool = False) -> str:
    state = list(plan.snapshot)
    for move in plan.moves:
        if move.kind is MoveKind.SHATTER:
            _shatter(state, move.layer)
        else:
            _descend(state, move.layer)
    if include_event and plan.event_source is not None:
        source = plan.event_source
        target = plan.event_target
        assert target is not None
        # Event witnesses are compiled separately by C7.  At component level,
        # all sacrificial runs have already been made empty by the event.
        for lo, hi in _runs("".join(state)):
            for i in range(lo, hi):
                state[i] = "-"
        if state[source] != "S" or state[target] != "-":
            raise RegionPlanError(
                f"bad event move {source}->{target}: {''.join(state)}"
            )
        state[source] = "-"
        state[target] = "S"
    for move in plan.post_moves:
        if move.kind is MoveKind.SHATTER:
            _shatter(state, move.layer)
        else:
            _descend(state, move.layer)
    return "".join(state)


def _remaining_shatters(snapshot: str, scheduled: list[RegionMove]) -> list[RegionMove]:
    state = list(snapshot)
    for move in scheduled:
        if move.kind is MoveKind.SHATTER:
            _shatter(state, move.layer)
        else:
            _descend(state, move.layer)
    return [RegionMove(MoveKind.SHATTER, lo) for lo, _ in _runs("".join(state))]


def _dropper_chain_plan(target: str, kind: RegionKind) -> RegionPlan:
    """The topmost-SS/dropper-chain witness shared by segments and zones."""
    s = len(target)
    adjacent = [i for i in range(s - 1) if target[i:i + 2] == "SS"]
    if not adjacent or target.endswith("S"):
        raise RegionPlanError("dropper-chain precondition")
    a = adjacent[-1]
    positions = [i for i, ch in enumerate(target) if ch == "S"]
    upper = [i for i in positions if i > a + 1]
    q = {i for i in positions if i <= a}
    q.update(i - 1 for i in upper)
    q.add(s - 1)
    snapshot = "".join("S" if i in q else "c" for i in range(s))
    moves: list[RegionMove] = []
    if upper:
        moves.append(RegionMove(MoveKind.SHATTER, upper[-1]))
        moves.append(RegionMove(MoveKind.DESCEND, s - 1))
        for j in range(len(upper) - 1, 0, -1):
            moves.append(RegionMove(MoveKind.SHATTER, upper[j - 1]))
            moves.append(RegionMove(MoveKind.DESCEND, upper[j] - 1))
        moves.append(RegionMove(MoveKind.SHATTER, a + 1))
        moves.append(RegionMove(MoveKind.DESCEND, upper[0] - 1))
    else:
        moves.append(RegionMove(MoveKind.SHATTER, a + 1))
        moves.append(RegionMove(MoveKind.DESCEND, s - 1))
    moves.extend(_remaining_shatters(snapshot, moves))
    plan = RegionPlan(kind, target, snapshot, tuple(moves))
    actual = replay_region(plan)
    if actual != target:
        raise RegionPlanError((target, snapshot, moves, actual))
    return plan


def natural_segment_plan(segment: str) -> RegionPlan:
    if not is_i_nat(segment):
        raise RegionPlanError(f"not I_nat: {segment!r}")
    if segment in ("", "S"):
        return RegionPlan(RegionKind.SEGMENT, segment, segment, ())
    if segment.endswith("S"):
        snapshot = segment.replace("-", "c")
        moves = tuple(RegionMove(MoveKind.SHATTER, lo) for lo, _ in _runs(snapshot))
        return RegionPlan(RegionKind.SEGMENT, segment, snapshot, moves)
    return _dropper_chain_plan(segment, RegionKind.SEGMENT)


def natural_zone_body_plan(body: str) -> RegionPlan:
    """Natural route for the pin-free body v of Z=P^a v."""
    dead = bool(body) and body.startswith("-") and body.endswith("-") and "SS" not in body
    if dead:
        raise RegionPlanError(f"dead natural zone: {body!r}")
    if body == "":
        return RegionPlan(RegionKind.ZONE, body, body, ())
    if body.endswith("S"):
        snapshot = body.replace("-", "c")
        moves = tuple(RegionMove(MoveKind.SHATTER, lo) for lo, _ in _runs(snapshot))
        return RegionPlan(RegionKind.ZONE, body, snapshot, moves)
    if "SS" in body:
        return _dropper_chain_plan(body, RegionKind.ZONE)

    # Floor-domino family: starts S, ends gap, all S isolated.
    positions = [i for i, ch in enumerate(body) if ch == "S"]
    if not positions or positions[0] != 0:
        raise RegionPlanError(f"not a natural zone case: {body!r}")
    z = len(body)
    q = {p - 1 for p in positions[1:]}
    q.add(z - 1)
    snapshot = "".join("S" if i in q else "c" for i in range(z))
    moves: list[RegionMove] = []
    if len(positions) == 1:
        moves.append(RegionMove(MoveKind.SHATTER, 0))
        moves.append(RegionMove(MoveKind.DESCEND, z - 1))
    else:
        moves.append(RegionMove(MoveKind.SHATTER, positions[-1]))
        moves.append(RegionMove(MoveKind.DESCEND, z - 1))
        for j in range(len(positions) - 2, 0, -1):
            moves.append(RegionMove(MoveKind.SHATTER, positions[j]))
            moves.append(RegionMove(MoveKind.DESCEND, positions[j + 1] - 1))
        moves.append(RegionMove(MoveKind.SHATTER, 0))
        moves.append(RegionMove(MoveKind.DESCEND, positions[1] - 1))
    moves.extend(_remaining_shatters(snapshot, moves))
    plan = RegionPlan(RegionKind.ZONE, body, snapshot, tuple(moves))
    actual = replay_region(plan)
    if actual != body:
        raise RegionPlanError((body, snapshot, moves, actual))
    return plan


def event_segment_plan(segment: str) -> RegionPlan:
    if not is_i_weak(segment):
        raise RegionPlanError(f"not I_weak: {segment!r}")
    if is_i_nat(segment):
        return natural_segment_plan(segment)
    positions = [i for i, ch in enumerate(segment) if ch == "S"]
    s = len(segment)
    q = set(positions[:-1])
    q.add(s - 1)
    snapshot = "".join("S" if i in q else "c" for i in range(s))
    source = s - 1
    target = positions[-1]
    plan = RegionPlan(
        RegionKind.SEGMENT,
        segment,
        snapshot,
        (),
        event_source=source,
        event_target=target,
    )
    actual = replay_region(plan, include_event=True)
    if actual != segment:
        raise RegionPlanError((segment, snapshot, source, target, actual))
    return plan

@dataclass(frozen=True)
class EventZonePlan:
    final_zone: str
    target_after_event: str
    post_lift_snapshot: str
    event_source: int | None
    event_target: int | None
    event_floor: bool
    post_moves: tuple[RegionMove, ...]
    remaining_plain_pushes: int
    case: str


def _replay_event_zone(plan: EventZonePlan) -> str:
    state = list(plan.post_lift_snapshot)
    # C7 relay coverage is chosen for every sacrificial c-run in the zone.
    for lo, hi in _runs(''.join(state)):
        for i in range(lo, hi):
            state[i] = '-'
    if plan.event_source is not None:
        source = plan.event_source
        target = plan.event_target
        assert target is not None
        if state[source] != 'S' or state[target] != '-':
            raise RegionPlanError(
                f"bad zone event {source}->{target}: {''.join(state)}"
            )
        state[source] = '-'
        state[target] = 'S'
    for move in plan.post_moves:
        if move.kind is MoveKind.SHATTER:
            _shatter(state, move.layer)
        else:
            _descend(state, move.layer)
    result = ''.join(state)
    if result != plan.target_after_event:
        raise RegionPlanError((plan, result))
    for _ in range(plan.remaining_plain_pushes):
        receipt = 'P' if result and result[0] != '-' else '-'
        result = receipt + result
    return result


def event_zone_plan(zone: str) -> EventZonePlan:
    """Exact event-route witness for a full zone ``P^a v``.

    Coordinates in ``post_lift_snapshot`` are after the event receipt has been
    prepended, matching :func:`compile_c7`.
    """
    a = 0
    while a < len(zone) and zone[a] == 'P':
        a += 1
    body = zone[a:]
    if set(body) - {'-', 'S'}:
        raise RegionPlanError(f"bad zone alphabet: {zone!r}")
    if not ('S' in body or (not body and a >= 1)):
        raise RegionPlanError(f"outside Z_evt: {zone!r}")
    if not (a >= 1 or body.count('-') >= 2):
        raise RegionPlanError(f"outside Z_evt: {zone!r}")

    if a >= 1:
        if not body:
            plan = EventZonePlan(
                zone, 'P', 'P', None, None, False, (), a - 1, 'pins_only'
            )
        else:
            homes = [i for i, ch in enumerate(body) if ch == 'S']
            z = len(body)
            q = set(homes[:-1])
            q.add(z - 1)
            body_snapshot = ''.join('S' if i in q else 'c' for i in range(z))
            source = z  # +1 for receipt, source body z-1
            target = homes[-1] + 1
            if source == target:
                source = target = None
            plan = EventZonePlan(
                zone,
                'P' + body,
                'P' + body_snapshot,
                source,
                target,
                False,
                (),
                a - 1,
                'p_receipt',
            )
        if _replay_event_zone(plan) != zone:
            raise RegionPlanError(plan)
        return plan

    # Pin-free event zone: body contains S and at least two gaps.
    homes = [i for i, ch in enumerate(body) if ch == 'S']
    z = len(body)
    dead = body.startswith('-') and body.endswith('-') and 'SS' not in body
    if not dead and homes[0] >= 2:
        # Natural alive body shifted up by the empty receipt.
        snapshot = ''.join('S' if i in homes else '-' for i in range(z))
        plan = EventZonePlan(
            zone, body, snapshot, None, None, False, (), 0, 'passive_receipt'
        )
    elif len(homes) == 1:
        source = z - 1
        target = homes[0]
        snapshot = ''.join('S' if i == source else '-' for i in range(z))
        plan = EventZonePlan(
            zone, body, snapshot, source, target, target == 0, (), 0, 'top_parking'
        )
    elif homes[1] >= 3:
        pre_positions = {homes[1] - 2, homes[1] - 1}
        pre_positions.update(p - 1 for p in homes[2:])
        post_positions = {p + 1 for p in pre_positions}
        source = homes[1] - 1
        target = homes[0]
        snapshot = ''.join('S' if i in post_positions else '-' for i in range(z))
        plan = EventZonePlan(
            zone, body, snapshot, source, target, target == 0, (), 0, 'pair_assembly'
        )
    else:
        # Bottom-packed block.  homes are zero-based p_i; the proof's i is
        # one-based.  b is the largest count such that p_i <= i.
        b = 0
        for idx, p in enumerate(homes, start=1):
            if p <= idx:
                b = idx
            else:
                break
        if b < 2:
            raise RegionPlanError(f"bad block-compaction case: {body!r}")
        pre_positions = set(range(1, b + 1))
        pre_positions.update(p - 1 for p in homes[b:])
        post_positions = {p + 1 for p in pre_positions}
        snapshot = ''.join('S' if i in post_positions else '-' for i in range(z))
        post_moves: list[RegionMove] = [
            RegionMove(MoveKind.DESCEND, source)
            for source in range(3, b + 2)
        ]
        d = 0
        if homes[0] == 0:
            for idx, p in enumerate(homes, start=1):
                if p == idx - 1:
                    d = idx
                else:
                    break
            post_moves.extend(
                RegionMove(MoveKind.DESCEND, source)
                for source in range(1, d + 1)
            )
        plan = EventZonePlan(
            zone,
            body,
            snapshot,
            2,
            1,
            False,
            tuple(post_moves),
            0,
            'block_compaction',
        )

    if _replay_event_zone(plan) != zone:
        raise RegionPlanError(plan)
    return plan
