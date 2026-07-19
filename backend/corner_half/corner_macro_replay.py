"""Concrete four-column replay for every Corner construction macro.

Helper *installation* is justified by the Exchange/Natural-Half lemmas; this
module verifies the actual game operation performed after installation.  Thus
it closes the gap between a one-dimensional component schedule and the
four-column physics used by the game.
"""
from __future__ import annotations

from dataclasses import dataclass

from .component_plans import MoveKind
from .corner_constructor import ConstructorKind, CornerConstructionCertificate
from .structural_ops import cut, generate, stack
from .structural_physics import (
    CRYSTAL, EMPTY, ORDINARY, PIN, code, column, is_stable, parse, push_pin,
)


class MacroReplayError(ValueError):
    pass


@dataclass(frozen=True)
class MacroReplayStep:
    rule: str
    detail: str
    a_before: str
    installed_shape: str
    operation_output: str
    a_after: str
    stable_before: bool
    stable_after: bool


@dataclass(frozen=True)
class CornerMacroReplay:
    target: str
    cap: int
    steps: tuple[MacroReplayStep,...]
    result: str
    replay_ok: bool


def _rows(cols:tuple[str,str,str,str],cap:int)->list[list[str]]:
    return [[cols[q][l] if l<len(cols[q]) else EMPTY for q in range(4)] for l in range(cap)]


def _a(rows:list[list[str]])->str:
    return column(rows,0)


def _tower(h:int, *, pin_layer:int|None=None, crystal_layer:int|None=None)->str:
    out=[ORDINARY]*h
    if pin_layer is not None:out[pin_layer]=PIN
    if crystal_layer is not None:out[crystal_layer]=CRYSTAL
    return ''.join(out)


def _record(rule,detail,before,installed,out)->MacroReplayStep:
    return MacroReplayStep(
        rule,detail,before,code(installed),code(out),_a(out),
        is_stable(installed),is_stable(out),
    )


def _deposit(a:str,layer:int,cell:str,cap:int)->tuple[str,MacroReplayStep]:
    if cell not in (ORDINARY,PIN):raise MacroReplayError('bad deposit cell')
    if not (0<=layer<cap):raise MacroReplayError('deposit outside cap')
    h=len(a)
    if cell==PIN and layer>0 and (layer-1>=len(a) or a[layer-1]==EMPTY):
        raise MacroReplayError('C1 pin would create -P')
    if layer<h and a[layer]!=EMPTY:raise MacroReplayError('deposit target occupied')

    if layer==h:
        helper_h=h
        bottom=_rows((a,_tower(helper_h),_tower(helper_h),_tower(helper_h)),cap)
        piece=[[cell,EMPTY,EMPTY,EMPTY]]
        out=stack(bottom,piece,cap)
        expected=a+cell
        rule='C1'
    else:
        if cell!=ORDINARY:raise MacroReplayError('only S can be anchored by C2')
        if layer<h:raise MacroReplayError('C2 layer must be above current top')
        bottom=_rows((a,_tower(layer),_tower(h),_tower(h)),cap)
        piece=[[ORDINARY,ORDINARY,EMPTY,EMPTY]]
        out=stack(bottom,piece,cap)
        expected=a+EMPTY*(layer-h)+ORDINARY
        rule='C2'
    actual=_a(out)
    if actual!=expected:raise MacroReplayError((rule,a,layer,cell,actual,expected,code(out)))
    step=_record(rule,f'deposit {cell} at {layer}',a,bottom,out)
    if not (step.stable_before and step.stable_after):raise MacroReplayError(step)
    return actual,step


def _generate(a:str,h_top:int,cap:int)->tuple[str,MacroReplayStep]:
    towers=_tower(h_top)
    before=_rows((a,towers,towers,towers),cap)
    out=generate(before,cap);actual=_a(out)
    expected=''.join(CRYSTAL if i<h_top and (i>=len(a) or a[i] in (EMPTY,PIN)) else (a[i] if i<len(a) else EMPTY) for i in range(h_top)).rstrip(EMPTY)
    if actual!=expected:raise MacroReplayError(('C3',a,h_top,actual,expected))
    step=_record('C3',f'generate below {h_top}',a,before,out)
    if not (step.stable_before and step.stable_after):raise MacroReplayError(step)
    return actual,step


def _shatter(a:str,layer:int,cap:int)->tuple[str,MacroReplayStep]:
    if not (0<=layer<len(a) and a[layer]==CRYSTAL):raise MacroReplayError('C4 no target crystal')
    h=max(len(a),layer+1)
    before=_rows((a,_tower(h),'',_tower(h,crystal_layer=layer)),cap)
    east,_=cut(before,cap);actual=_a(east)
    chars=list(a);lo=layer;hi=layer+1
    while lo>0 and chars[lo-1]==CRYSTAL:lo-=1
    while hi<len(chars) and chars[hi]==CRYSTAL:hi+=1
    for i in range(lo,hi):chars[i]=EMPTY
    expected=''.join(chars).rstrip(EMPTY)
    if actual!=expected:raise MacroReplayError(('C4',a,layer,actual,expected,code(before),code(east)))
    step=_record('C4',f'shatter run containing {layer}',a,before,east)
    if not (step.stable_before and step.stable_after):raise MacroReplayError(step)
    return actual,step


def _descend(a:str,source:int,cap:int)->tuple[str,MacroReplayStep]:
    if not (0<=source<len(a) and a[source]==ORDINARY):raise MacroReplayError('C5 no source S')
    h=max(len(a),source+1)
    before=_rows((a,_tower(h,pin_layer=source),'',_tower(h)),cap)
    east,_=cut(before,cap);actual=_a(east)
    chars=list(a);target=0
    for i in range(source-1,-1,-1):
        if chars[i]!=EMPTY:target=i+1;break
    if target>=source:raise MacroReplayError('C5 has no free descent')
    chars[source]=EMPTY;chars[target]=ORDINARY
    expected=''.join(chars).rstrip(EMPTY)
    if actual!=expected:raise MacroReplayError(('C5',a,source,actual,expected,code(before),code(east)))
    step=_record('C5',f'descend S from {source} to {target}',a,before,east)
    if not (step.stable_before and step.stable_after):raise MacroReplayError(step)
    return actual,step


def _push(a:str,cap:int)->tuple[str,MacroReplayStep]:
    if len(a)>=cap:raise MacroReplayError('C6 would overflow')
    h=len(a);tower=_tower(h)
    before=_rows((a,tower,tower,tower),cap)
    out=push_pin(before,cap);actual=_a(out)
    expected=((PIN if a and a[0]!=EMPTY else EMPTY)+a).rstrip(EMPTY)
    if actual!=expected:raise MacroReplayError(('C6',a,actual,expected))
    step=_record('C6','plain typed push',a,before,out)
    if not (step.stable_before and step.stable_after):raise MacroReplayError(step)
    return actual,step


def _build_skeleton(skeleton:str,cap:int)->tuple[str,list[MacroReplayStep]]:
    a='';steps=[]
    for layer,ch in enumerate(skeleton):
        if ch==ORDINARY:
            a,step=_deposit(a,layer,ORDINARY,cap);steps.append(step)
    return a,steps


def _append_top(a:str,top:str,cap:int)->tuple[str,list[MacroReplayStep]]:
    steps=[];base=len(a)
    for rel,ch in enumerate(top):
        if ch in (ORDINARY,PIN):
            a,step=_deposit(a,base+rel,ch,cap);steps.append(step)
    return a,steps


def replay_corner_certificate(cert:CornerConstructionCertificate)->CornerMacroReplay:
    steps:list[MacroReplayStep]=[]
    if cert.kind is ConstructorKind.NATURAL:
        assert cert.natural is not None
        p=cert.natural
        if not p.target:return CornerMacroReplay('',cert.cap,(),'',True)
        if 'c' not in p.snapshot:
            a,ss=_append_top('',p.target,cert.cap);steps+=ss
            if a!=p.target:raise MacroReplayError((a,p.target))
            return CornerMacroReplay(p.target,cert.cap,tuple(steps),a,True)
        a,ss=_build_skeleton(p.skeleton,cert.cap);steps+=ss
        a,st=_generate(a,len(p.snapshot),cert.cap);steps.append(st)
        if a!=p.snapshot:raise MacroReplayError(('snapshot',a,p.snapshot))
        for _ in range(p.pin_pushes):a,st=_push(a,cert.cap);steps.append(st)
        for move in p.moves:
            if move.kind is MoveKind.SHATTER:a,st=_shatter(a,move.layer,cert.cap)
            else:a,st=_descend(a,move.layer,cert.cap)
            steps.append(st)
        a,ss=_append_top(a,p.top,cert.cap);steps+=ss
    else:
        assert cert.event is not None and cert.event_predecessor is not None
        # All four predecessor columns have independently replayed natural plans;
        # their stable-half assembly is replayed by corner_constructor.
        for plan in cert.event_predecessor.column_plans:
            # Avoid recursive geometric assembly: these are natural-route plans.
            sub=CornerConstructionCertificate(plan.target,cert.cap,ConstructorKind.NATURAL,plan,None,None,None,plan.replay_ok)
            rep=replay_corner_certificate(sub)
            if not rep.replay_ok:raise MacroReplayError(rep)
        if cert.exchange_replay is None or not cert.exchange_replay.ok:
            raise MacroReplayError('event predecessor assembly failed')
        a=cert.event.c7.actual_a
        # Record C7 itself from the exact full predecessor/push replay.
        steps.append(MacroReplayStep(
            'C7','overflow event',cert.event.pre_push_a,
            cert.event.c7.predecessor,code(push_pin(parse(cert.event.c7.predecessor,cert.cap),cert.cap)),a,
            cert.event.c7.stable_predecessor,cert.event.c7.replay_ok,
        ))
        for move in cert.event.post_event_moves:
            if move.kind is MoveKind.SHATTER:a,st=_shatter(a,move.layer,cert.cap)
            else:a,st=_descend(a,move.layer,cert.cap)
            steps.append(st)
        for _ in range(cert.event.remaining_pushes):a,st=_push(a,cert.cap);steps.append(st)
        a,ss=_append_top(a,cert.event.top,cert.cap);steps+=ss
    ok=a==cert.target and all(s.stable_before and s.stable_after for s in steps)
    return CornerMacroReplay(cert.target,cert.cap,tuple(steps),a,ok)


__all__=['CornerMacroReplay','MacroReplayError','MacroReplayStep','replay_corner_certificate']
