"""Deterministic all-layer Corner construction certificates.

Proof stratification (no circularity):

* natural-route Corner uses only C1..C6;
* a stable half of two natural-route columns is constructible by the simple
  tower/swap/cut lemma;
* every C7 predecessor splits, in the orientation (B,C)|(D,A), into two such
  stable natural halves;
* one Swapper plus one rotation assembles A-B-C-D, then the C7 push finishes
  the event-route Corner;
* only after this is established is the general Half theorem allowed to use
  arbitrary (including event-route) Corner columns.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from .corner_dfa import first_rejection, is_craftable_column
from .corner_event_plan import CornerEventPlan, compile_corner_event
from .corner_natural_plan import CornerNaturalPlan, compile_corner_natural
from .corner_regions import Route, analyze_column
from .structural_physics import EMPTY, code, is_stable, parse


class ConstructorKind(str, Enum):
    NATURAL="natural"
    EVENT="event"


@dataclass(frozen=True)
class NaturalHalfProof:
    first: CornerNaturalPlan
    second: CornerNaturalPlan
    stable: bool
    orientation: str


@dataclass(frozen=True)
class EventPredecessorProof:
    column_plans: tuple[
        CornerNaturalPlan,CornerNaturalPlan,CornerNaturalPlan,CornerNaturalPlan
    ]
    half_bc: NaturalHalfProof
    half_da: NaturalHalfProof
    assembly_sequence: tuple[str,...]


@dataclass(frozen=True)
class ExchangeReplay:
    prefab_bc: str
    prefab_da: str
    after_swap: str
    final: str
    target_predecessor: str
    ok: bool


@dataclass(frozen=True)
class CornerConstructionCertificate:
    target: str
    cap: int
    kind: ConstructorKind
    natural: CornerNaturalPlan|None
    event: CornerEventPlan|None
    event_predecessor: EventPredecessorProof|None
    exchange_replay: ExchangeReplay|None
    replay_ok: bool


class CornerConstructionError(ValueError):
    pass


def _rows_from_columns(columns:tuple[str,str,str,str],cap:int)->list[list[str]]:
    return [[columns[q][l] if l<len(columns[q]) else EMPTY for q in range(4)] for l in range(cap)]


def _half_stable(rows:list[list[str]],q0:int,q1:int)->bool:
    keep={q0,q1}
    return is_stable([[cell if q in keep else EMPTY for q,cell in enumerate(row)] for row in rows])


def replay_event_exchange(event:CornerEventPlan)->ExchangeReplay:
    """Assemble the C7 predecessor from stable natural halves BC and DA."""
    from .structural_ops import rotate,swap
    cap=event.cap
    a,b,c,d=event.c7.predecessor_columns
    prefab_bc=_rows_from_columns((b,c,"",""),cap)
    prefab_da=_rows_from_columns(("","",d,a),cap)
    if not (is_stable(prefab_bc) and is_stable(prefab_da)):
        return ExchangeReplay(code(prefab_bc),code(prefab_da),"","",event.c7.predecessor,False)
    joined,_=swap(prefab_bc,prefab_da,cap)  # B,C,D,A
    final=rotate(joined,1)                  # A,B,C,D
    final_code=code(final)
    return ExchangeReplay(
        code(prefab_bc),code(prefab_da),code(joined),final_code,
        event.c7.predecessor,
        final_code==event.c7.predecessor and is_stable(final),
    )


@lru_cache(maxsize=200_000)
def construct_corner(column:str,cap:int|None=None)->CornerConstructionCertificate:
    normalized=column.rstrip(EMPTY)
    if not is_craftable_column(normalized):
        rejection=first_rejection(normalized)
        assert rejection is not None
        raise CornerConstructionError(f"forbidden {rejection.rule} at {rejection.position}")
    if cap is None:cap=max(1,len(normalized))
    if len(normalized)>cap:raise CornerConstructionError("column exceeds cap")
    witness=analyze_column(normalized)
    if witness.route in (Route.CRYSTAL_FREE,Route.NATURAL):
        natural=compile_corner_natural(normalized,cap)
        return CornerConstructionCertificate(
            normalized,cap,ConstructorKind.NATURAL,natural,None,None,None,natural.replay_ok
        )

    event=compile_corner_event(normalized,cap)
    a,b,c,d=event.c7.predecessor_columns
    values=(a,b,c,d)
    plans=[]
    for value in values:
        if analyze_column(value).route is Route.EVENT:
            raise CornerConstructionError(f"C7 predecessor helper is event-route: {value!r}")
        plan=compile_corner_natural(value,cap)
        if not plan.replay_ok:raise CornerConstructionError(f"natural helper failed: {value!r}")
        plans.append(plan)

    rows=parse(event.c7.predecessor,cap)
    bc=_half_stable(rows,1,2)
    da=_half_stable(rows,3,0)
    if not (bc and da):
        raise CornerConstructionError(f"C7 split not stable: BC={bc}, DA={da}")
    proof=EventPredecessorProof(
        tuple(plans),
        NaturalHalfProof(plans[1],plans[2],bc,"B,C"),
        NaturalHalfProof(plans[3],plans[0],da,"D,A"),
        (
            "construct stable natural half (B,C)",
            "construct stable natural half (D,A)",
            "swap to obtain (B,C,D,A)",
            "rotate clockwise to obtain (A,B,C,D)",
            "apply the certified C7 Pin Pusher",
        ),
    )
    exchange=replay_event_exchange(event)
    ok=event.replay_ok and all(p.replay_ok for p in plans) and exchange.ok
    return CornerConstructionCertificate(
        normalized,cap,ConstructorKind.EVENT,None,event,proof,exchange,ok
    )


__all__=[
    "ConstructorKind","CornerConstructionCertificate","CornerConstructionError",
    "EventPredecessorProof","ExchangeReplay","NaturalHalfProof",
    "construct_corner","replay_event_exchange",
]
