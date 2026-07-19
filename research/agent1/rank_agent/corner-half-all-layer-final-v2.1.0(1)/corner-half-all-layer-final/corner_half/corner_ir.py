"""Deterministic merge IR for the complete Corner constructor.

The mathematical constructor is expressed with derived rules C1..C7.  This
module lowers every accepted column to a finite, replayed linear program whose
steps carry the exact target-column before/after state and the helper prefab
class needed by the integration branch.  Primitive prefab implementations are
in :mod:`primitive_prefabs`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .component_plans import MoveKind
from .corner_constructor import ConstructorKind, construct_corner
from .corner_dfa import first_rejection, is_craftable_column
from .corner_regions import analyze_column


class CornerRule(str, Enum):
    C1_TOP_DEPOSIT = "C1_top_deposit"
    C2_ANCHORED_DEPOSIT = "C2_anchored_deposit"
    C3_GENERATE = "C3_generate"
    C4_SHATTER = "C4_shatter"
    C5_DESCEND = "C5_pin_cut_descent"
    C6_PUSH = "C6_typed_push"
    C7_EVENT = "C7_overflow_event"


@dataclass(frozen=True)
class CornerIRStep:
    rule: CornerRule
    before: str
    after: str
    layer: int | None = None
    helper: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CornerRuleProgram:
    target: str
    cap: int
    kind: ConstructorKind
    steps: tuple[CornerIRStep, ...]
    required_prefabs: tuple[str, ...]
    final_column: str
    replay_ok: bool


class CornerIRError(ValueError):
    pass


def _trim(value: str) -> str:
    return value.rstrip("-")


def _set_at(value: str, layer: int, cell: str) -> str:
    state=list(value)
    while len(state)<=layer:state.append('-')
    if state[layer] != '-':
        raise CornerIRError(f"cell {layer} already occupied in {value!r}")
    state[layer]=cell
    return _trim(''.join(state))


def _shatter(value: str, layer: int) -> str:
    state=list(value)
    if not (0<=layer<len(state)) or state[layer]!='c':
        raise CornerIRError(f"no crystal at {layer} in {value!r}")
    lo=layer
    while lo>0 and state[lo-1]=='c':lo-=1
    hi=layer+1
    while hi<len(state) and state[hi]=='c':hi+=1
    for i in range(lo,hi):state[i]='-'
    return _trim(''.join(state))


def _descend(value: str, source: int) -> str:
    state=list(value)
    if not (0<=source<len(state)) or state[source]!='S':
        raise CornerIRError(f"no S at {source} in {value!r}")
    target=0
    for i in range(source-1,-1,-1):
        if state[i] != '-':target=i+1;break
    if target>=source or state[target]!='-':
        raise CornerIRError(f"cannot descend {source} in {value!r}")
    state[source]='-';state[target]='S'
    return _trim(''.join(state))


def _push(value: str) -> str:
    return _trim(('P' if value and value[0]!='-' else '-')+value)


def _deposit_steps(state: str, desired: str, start: int, steps: list[CornerIRStep]) -> str:
    """Place desired crystal-free cells at absolute layers starting at start."""
    for rel,cell in enumerate(desired):
        if cell=='-':continue
        layer=start+rel
        below = layer==0 or (layer-1 < len(state) and state[layer-1] != '-')
        if cell=='P' and not below:
            raise CornerIRError("-P would require an impossible anchored pin")
        rule=CornerRule.C1_TOP_DEPOSIT if below else CornerRule.C2_ANCHORED_DEPOSIT
        helper="one_pin_piece" if cell=='P' else (
            "one_ordinary_piece" if below else "two_ordinary_anchor_piece"
        )
        after=_set_at(state,layer,cell)
        steps.append(CornerIRStep(rule,state,after,layer,helper))
        state=after
    return state


def _lower_natural(column: str, cap: int, steps: list[CornerIRStep]) -> str:
    from .corner_natural_plan import compile_corner_natural
    plan=compile_corner_natural(column,cap)
    witness=analyze_column(column)
    if not witness.regions.crystal_positions:
        return _deposit_steps('',plan.target,0,steps)

    state=_deposit_steps('',plan.skeleton,0,steps)
    generated=plan.snapshot
    steps.append(CornerIRStep(
        CornerRule.C3_GENERATE,state,generated,None,"generator",
    ))
    state=generated
    for _ in range(plan.pin_pushes):
        after=_push(state)
        steps.append(CornerIRStep(
            CornerRule.C6_PUSH,state,after,None,"solid_support_towers",
        ))
        state=after
    for move in plan.moves:
        if move.kind is MoveKind.SHATTER:
            after=_shatter(state,move.layer)
            rule=CornerRule.C4_SHATTER;helper="single_crystal_trigger_helper"
        else:
            after=_descend(state,move.layer)
            rule=CornerRule.C5_DESCEND;helper="solid_tower_with_one_pin"
        steps.append(CornerIRStep(rule,state,after,move.layer,helper))
        state=after
    state=_deposit_steps(state,plan.top,len(state),steps)
    if state != plan.target:
        raise CornerIRError((column,state,plan.target))
    return state


def compile_corner_ir(column: str, cap: int | None = None) -> CornerRuleProgram:
    if not is_craftable_column(column):
        rejection=first_rejection(column)
        assert rejection is not None
        raise CornerIRError(f"forbidden {rejection.rule} at {rejection.position}")
    target=_trim(column)
    if cap is None:cap=max(1,len(target))
    certificate=construct_corner(target,cap)
    steps:list[CornerIRStep]=[]
    if certificate.kind is ConstructorKind.NATURAL:
        state=_lower_natural(target,cap,steps)
    else:
        assert certificate.event is not None
        event=certificate.event
        state=_lower_natural(event.pre_push_a,cap,steps)
        if state != event.pre_push_a:
            raise CornerIRError((state,event.pre_push_a))
        after=event.c7.actual_a
        steps.append(CornerIRStep(
            CornerRule.C7_EVENT,state,after,None,"C7_B_C_D",
            (("predecessor",event.c7.predecessor),
             ("duties",str(tuple((d.source,d.target,d.kind.value) for d in event.duties)))),
        ))
        state=after
        for move in event.post_event_moves:
            if move.kind is MoveKind.SHATTER:
                after=_shatter(state,move.layer)
                rule=CornerRule.C4_SHATTER;helper="single_crystal_trigger_helper"
            else:
                after=_descend(state,move.layer)
                rule=CornerRule.C5_DESCEND;helper="solid_tower_with_one_pin"
            steps.append(CornerIRStep(rule,state,after,move.layer,helper))
            state=after
        for _ in range(event.remaining_pushes):
            after=_push(state)
            steps.append(CornerIRStep(
                CornerRule.C6_PUSH,state,after,None,"solid_support_towers",
            ))
            state=after
        state=_deposit_steps(state,event.top,len(state),steps)
    required=tuple(sorted({step.helper for step in steps if step.helper}))
    ok=certificate.replay_ok and state==target and all(step.before == (steps[i-1].after if i else '') for i,step in enumerate(steps))
    # For event programs, _lower_natural prelude starts at empty too, so the
    # continuity check above remains valid.
    return CornerRuleProgram(target,cap,certificate.kind,tuple(steps),required,state,ok)


__all__=[
    "CornerRule", "CornerIRStep", "CornerRuleProgram", "CornerIRError",
    "compile_corner_ir",
]
