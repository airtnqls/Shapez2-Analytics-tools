"""Whole-column event-route lowering into the concrete C7 compiler.

The plan deliberately chooses a pre-push A column that is on the natural
route.  Lower sacrificial runs are removed before the event; only the crystal
run needed for each anchored faller (and, for a P receipt, a possible bottom
run) remains.  Thus C7 needs exactly the separated duties handled by
:mod:`c7_gadget`.
"""
from __future__ import annotations

from dataclasses import dataclass

from .c7_gadget import C7Certificate, C7Duty, DutyKind, compile_c7
from .component_plans import (
    EventZonePlan,
    MoveKind,
    RegionMove,
    event_segment_plan,
    event_zone_plan,
)
from .corner_regions import Route, analyze_column, factor_column, is_i_nat


class EventPlanError(ValueError):
    pass


@dataclass(frozen=True)
class AbsoluteMove:
    kind: MoveKind
    layer: int


@dataclass(frozen=True)
class CornerEventPlan:
    target: str
    cap: int
    pre_push_a: str
    post_lift_a: str
    duties: tuple[C7Duty, ...]
    c7: C7Certificate
    post_event_moves: tuple[AbsoluteMove, ...]
    after_post_moves: str
    remaining_pushes: int
    core_after_pushes: str
    top: str
    replay_ok: bool


def _runs(s: str) -> list[tuple[int, int]]:
    out=[]
    i=0
    while i < len(s):
        if s[i] != 'c':
            i += 1
            continue
        j=i+1
        while j < len(s) and s[j]=='c':
            j += 1
        out.append((i,j)); i=j
    return out


def _runs_touching(s: str, touched: set[int]) -> set[int]:
    out=set()
    for lo,hi in _runs(s):
        if any(i in touched for i in range(lo,hi)):
            out.update(range(lo,hi))
    return out


def _retain_event_crystals(snapshot: str, source: int | None, target: int | None, *, keep_bottom: bool) -> str:
    keep:set[int]=set()
    if source is not None:
        assert target is not None
        keep |= _runs_touching(snapshot, set(range(target, source)))
    if keep_bottom and snapshot and snapshot[0]=='c':
        lo,hi=_runs(snapshot)[0]
        if lo==0:
            keep.update(range(lo,hi))
    return ''.join(ch if ch!='c' or i in keep else '-' for i,ch in enumerate(snapshot))


def _shatter(state:list[str], layer:int)->None:
    if not (0 <= layer < len(state)) or state[layer] != 'c':
        raise EventPlanError(f'no c at {layer}: {"".join(state)}')
    lo=layer
    while lo>0 and state[lo-1]=='c': lo-=1
    hi=layer+1
    while hi<len(state) and state[hi]=='c': hi+=1
    for i in range(lo,hi): state[i]='-'


def _descend(state:list[str], source:int)->int:
    if not (0 <= source < len(state)) or state[source]!='S':
        raise EventPlanError(f'no S at {source}: {"".join(state)}')
    target=0
    for i in range(source-1,-1,-1):
        if state[i] != '-':
            target=i+1; break
    if target>=source or state[target] != '-':
        raise EventPlanError(f'cannot descend {source}: {"".join(state)}')
    state[source]='-'; state[target]='S'; return target


def _plain_push_column(s: str) -> str:
    receipt = 'P' if s and s[0] != '-' else '-'
    return (receipt + s).rstrip('-')



def _natural_blocker_survives(post_event: str, source: int, target: int) -> bool:
    state = list(post_event)
    touched = set(range(target, source))
    for lo, hi in _runs(post_event):
        if any(i in touched for i in range(lo, hi)):
            for i in range(lo, hi):
                state[i] = '-'
    return target > 0 and state[target - 1] != '-'

def _zone_pre_and_duty(zone_plan: EventZonePlan) -> tuple[str, C7Duty | None]:
    post = zone_plan.post_lift_snapshot
    if not post:
        raise EventPlanError('empty event post snapshot')
    if post[0] not in '-P':
        raise EventPlanError('event snapshot lacks receipt row')

    if post[0] == 'P':
        body_snapshot = post[1:]
        source = None if zone_plan.event_source is None else zone_plan.event_source - 1
        target = None if zone_plan.event_target is None else zone_plan.event_target - 1
        # A bottom run must survive until the event to type the P receipt.
        body_event = _retain_event_crystals(
            body_snapshot, source, target, keep_bottom=True
        )
        post_event = 'P' + body_event
        pre = body_event
        if zone_plan.event_source is None:
            duty=None
        else:
            target_abs = zone_plan.event_target or 0
            if zone_plan.event_floor:
                kind = DutyKind.FLOOR
            elif _natural_blocker_survives(post_event, zone_plan.event_source, target_abs):
                kind = DutyKind.NATURAL
            else:
                kind = DutyKind.ANCHORED
            duty=C7Duty(zone_plan.event_source, target_abs, kind)
    else:
        # Empty receipt: the pre-push zone is exactly the post snapshot without
        # row zero.  These witnesses are crystal-free at event time.
        post_event = post
        pre = post[1:]
        if zone_plan.event_source is None:
            duty=None
        else:
            target_abs = zone_plan.event_target or 0
            if zone_plan.event_floor:
                kind = DutyKind.FLOOR
            elif _natural_blocker_survives(post_event, zone_plan.event_source, target_abs):
                kind = DutyKind.NATURAL
            else:
                kind = DutyKind.ANCHORED
            duty=C7Duty(zone_plan.event_source, target_abs, kind)
    # sanity: shifting pre recreates the selected event-time zone
    # For the pins-only zone, the following lowest keeper (outside this
    # local zone slice) is the occupied pre-push bottom and types the P
    # receipt.  Other cases are locally decidable here.
    if not (post == 'P' and pre == ''):
        receipt='P' if pre and pre[0]!='-' else '-'
        if (receipt+pre).rstrip('-') != post_event.rstrip('-'):
            raise EventPlanError((zone_plan, pre, post_event, receipt+pre))
    return pre, duty


def compile_corner_event(column: str, cap: int | None = None) -> CornerEventPlan:
    witness=analyze_column(column)
    if witness.route is not Route.EVENT:
        raise EventPlanError('column is not on the event route')
    regions=witness.regions
    target=regions.column
    if cap is None: cap=max(1,len(target))
    if len(target)>cap:
        raise EventPlanError('target exceeds cap')
    assert witness.zone is not None
    zplan=event_zone_plan(regions.zone)
    pre_zone, zone_duty = _zone_pre_and_duty(zplan)

    pre_parts=[pre_zone]
    duties:list[C7Duty]=[]
    if zone_duty is not None:
        duties.append(zone_duty)

    # post-lift offset of the lowest keeper is the event-zone target length.
    post_zone_len=len(zplan.target_after_event)
    post_cursor=post_zone_len
    pre_parts.append('c')  # lowest kept crystal
    post_cursor += 1

    for idx, segment in enumerate(regions.segments):
        splan=event_segment_plan(segment)
        if splan.event_source is None:
            pre_segment=segment
        else:
            pre_segment=_retain_event_crystals(
                splan.snapshot,
                splan.event_source,
                splan.event_target,
                keep_bottom=False,
            )
            duties.append(C7Duty(
                post_cursor + splan.event_source,
                post_cursor + (splan.event_target or 0),
                DutyKind.ANCHORED,
            ))
        pre_parts.append(pre_segment)
        post_cursor += len(segment)
        pre_parts.append('c')
        post_cursor += 1

    pre_push_a=''.join(pre_parts).rstrip('-')
    # The chosen pre-event A must be reachable without an overflow event.
    pre_witness=analyze_column(pre_push_a)
    if pre_witness.route is Route.EVENT:
        raise EventPlanError(
            f'pre-event A is not natural: target={target}, pre={pre_push_a}'
        )

    receipt='P' if pre_push_a and pre_push_a[0]!='-' else '-'
    post_lift_a=(receipt+pre_push_a).rstrip('-')
    c7=compile_c7(post_lift_a,cap,duties)
    state=list(c7.actual_a)
    moves:list[AbsoluteMove]=[]

    # Any P-receipt bottom sacrificial run deliberately survived C7 when it was
    # separate from the zone faller path.  Remove all remaining zone crystals.
    zone_limit=len(zplan.target_after_event)
    pos=0
    while pos < min(zone_limit,len(state)):
        if state[pos]=='c':
            moves.append(AbsoluteMove(MoveKind.SHATTER,pos))
            _shatter(state,pos)
        else:
            pos += 1

    for move in zplan.post_moves:
        absolute=move.layer
        moves.append(AbsoluteMove(move.kind,absolute))
        if move.kind is MoveKind.SHATTER:
            _shatter(state,absolute)
        else:
            _descend(state,absolute)

    after_post=''.join(state).rstrip('-')
    core_target_after_event=(
        zplan.target_after_event
        + 'c'
        + 'c'.join(regions.segments)
        + ('c' if regions.crystal_positions else '')
    )
    # The expression above duplicates the first keeper when there are no
    # segments? Build it directly from the factorization instead.
    core_target_after_event = zplan.target_after_event
    for segment in regions.segments:
        core_target_after_event += 'c' + segment
    core_target_after_event += 'c'
    if after_post != core_target_after_event:
        raise EventPlanError((target, pre_push_a, after_post, core_target_after_event, c7))

    core=after_post
    for _ in range(zplan.remaining_plain_pushes):
        if len(core)>=cap:
            raise EventPlanError('plain post-event push would overflow')
        core=_plain_push_column(core)
    target_core=target[:regions.crystal_positions[-1]+1]
    if core != target_core:
        raise EventPlanError((target, core, target_core, zplan))

    replay=(core + regions.top) == target
    return CornerEventPlan(
        target=target,
        cap=cap,
        pre_push_a=pre_push_a,
        post_lift_a=post_lift_a,
        duties=tuple(duties),
        c7=c7,
        post_event_moves=tuple(moves),
        after_post_moves=after_post,
        remaining_pushes=zplan.remaining_plain_pushes,
        core_after_pushes=core,
        top=regions.top,
        replay_ok=replay and c7.replay_ok,
    )
