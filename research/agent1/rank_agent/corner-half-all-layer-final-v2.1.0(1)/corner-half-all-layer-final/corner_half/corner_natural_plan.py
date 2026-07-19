"""Exact natural-route Corner constructor schedule.

The schedule is a direct executable form of §6.3/§6.4:

1. place S at every snapshot-S location and leave future crystals empty;
2. run one Generator, obtaining ``snapshot``;
3. execute the component C4/C5 moves;
4. perform the bottom pin-prefix pushes;
5. deposit the crystal-free top region.

The module replays the one-dimensional effect exactly.  Each move corresponds
to the concrete C1..C6 macro whose four-column realization is stated in the
column theorem.
"""
from __future__ import annotations

from dataclasses import dataclass

from .component_plans import MoveKind, natural_segment_plan, natural_zone_body_plan
from .corner_regions import Route, analyze_column


class NaturalPlanError(ValueError):
    pass


@dataclass(frozen=True)
class NaturalMove:
    kind: MoveKind
    layer: int


@dataclass(frozen=True)
class CornerNaturalPlan:
    target: str
    cap: int
    skeleton: str
    snapshot: str
    moves: tuple[NaturalMove, ...]
    pin_pushes: int
    top: str
    core_after_moves: str
    core_after_pushes: str
    replay_ok: bool


def _shatter(state: list[str], layer: int) -> None:
    if not (0 <= layer < len(state)) or state[layer] != 'c':
        raise NaturalPlanError(f'no c at {layer}: {"".join(state)}')
    lo=layer
    while lo>0 and state[lo-1]=='c': lo-=1
    hi=layer+1
    while hi<len(state) and state[hi]=='c': hi+=1
    for i in range(lo,hi): state[i]='-'


def _descend(state: list[str], source: int) -> int:
    if not (0 <= source < len(state)) or state[source]!='S':
        raise NaturalPlanError(f'no S at {source}: {"".join(state)}')
    target=0
    for i in range(source-1,-1,-1):
        if state[i]!='-': target=i+1;break
    if target>=source or state[target]!='-':
        raise NaturalPlanError(f'cannot descend {source}: {"".join(state)}')
    state[source]='-';state[target]='S';return target


def _plain_push(s: str) -> str:
    return (('P' if s and s[0]!='-' else '-')+s).rstrip('-')


def compile_corner_natural(column: str, cap: int | None = None) -> CornerNaturalPlan:
    witness=analyze_column(column)
    if witness.route not in (Route.CRYSTAL_FREE,Route.NATURAL):
        raise NaturalPlanError('not a natural-route column')
    target=witness.regions.column
    if cap is None: cap=max(1,len(target))
    if len(target)>cap: raise NaturalPlanError('target exceeds cap')

    if witness.route is Route.CRYSTAL_FREE:
        # C1/C2 deposits directly realize every -P-free crystal-free column.
        return CornerNaturalPlan(
            target,cap,target,target,(),0,'',target,target,True
        )

    regions=witness.regions
    assert witness.zone is not None
    a=witness.zone.pin_count
    body=witness.zone.body
    zplan=natural_zone_body_plan(body)

    snapshot_parts=[zplan.snapshot]
    moves:list[NaturalMove]=[
        NaturalMove(m.kind,m.layer) for m in zplan.moves
    ]
    cursor=len(body)
    snapshot_parts.append('c')
    cursor+=1
    for segment in regions.segments:
        plan=natural_segment_plan(segment)
        snapshot_parts.append(plan.snapshot)
        moves.extend(NaturalMove(m.kind,cursor+m.layer) for m in plan.moves)
        cursor+=len(segment)
        snapshot_parts.append('c')
        cursor+=1
    snapshot=''.join(snapshot_parts)
    skeleton=''.join('S' if ch=='S' else '-' for ch in snapshot)

    # Natural-zone pins are inserted while the snapshot bottom is still
    # occupied (possibly by a sacrificial bottom crystal).  Therefore the
    # plain pushes precede all C4/C5 moves and shift their coordinates.
    pushed_snapshot=snapshot
    for _ in range(a):
        if len(pushed_snapshot)>=cap:
            raise NaturalPlanError('plain push would overflow')
        pushed_snapshot=_plain_push(pushed_snapshot)
    shifted_moves=tuple(NaturalMove(m.kind,m.layer+a) for m in moves)

    state=list(pushed_snapshot)
    for move in shifted_moves:
        if move.kind is MoveKind.SHATTER:_shatter(state,move.layer)
        else:_descend(state,move.layer)
    core=''.join(state).rstrip('-')
    target_core=target[:regions.crystal_positions[-1]+1]
    if core!=target_core:
        raise NaturalPlanError((target,pushed_snapshot,shifted_moves,core,target_core))
    replay=(core+regions.top)==target
    return CornerNaturalPlan(
        target=target,
        cap=cap,
        skeleton=skeleton,
        snapshot=snapshot,
        moves=shifted_moves,
        pin_pushes=a,
        top=regions.top,
        core_after_moves=core,
        core_after_pushes=core,
        replay_ok=replay,
    )
