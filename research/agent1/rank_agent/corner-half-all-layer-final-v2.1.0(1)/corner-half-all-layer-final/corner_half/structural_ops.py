"""Exact structural forward operations used by Corner/Half certificates."""
from __future__ import annotations

from typing import Sequence

from .structural_physics import (
    CRYSTAL, EMPTY, ORDINARY, PIN, apply_gravity, crystal_component,
    get, occupied, trim,
)


def _fixed(rows: Sequence[Sequence[str]], cap: int) -> list[list[str]]:
    out=[list(r) for r in rows[:cap]]
    while len(out)<cap:out.append([EMPTY]*4)
    return out


def rotate(rows: Sequence[Sequence[str]], steps_cw: int = 1) -> list[list[str]]:
    k=steps_cw%4
    out=[list(r) for r in rows]
    for _ in range(k):
        out=[[r[3],r[0],r[1],r[2]] for r in out]
    return trim(out)


def _cut_seeds(rows: Sequence[Sequence[str]]) -> set[tuple[int,int]]:
    seeds=set()
    for l,row in enumerate(rows):
        for a,b in ((1,2),(3,0)):
            if row[a]==CRYSTAL and row[b]==CRYSTAL:
                seeds.add((l,a));seeds.add((l,b))
    return seeds


def cut(rows: Sequence[Sequence[str]], cap: int) -> tuple[list[list[str]],list[list[str]]]:
    work=_fixed(rows,cap)
    shattered=crystal_component(work,_cut_seeds(work))
    for l,q in shattered:work[l][q]=EMPTY
    east=[];west=[]
    for row in work:
        east.append([row[0],row[1],EMPTY,EMPTY])
        west.append([EMPTY,EMPTY,row[2],row[3]])
    return apply_gravity(east),apply_gravity(west)


def combine(east: Sequence[Sequence[str]], west: Sequence[Sequence[str]], cap:int)->list[list[str]]:
    a=_fixed(east,cap);b=_fixed(west,cap)
    return trim([[a[l][0],a[l][1],b[l][2],b[l][3]] for l in range(cap)])


def swap(a: Sequence[Sequence[str]], b: Sequence[Sequence[str]], cap:int)->tuple[list[list[str]],list[list[str]]]:
    ae,aw=cut(a,cap);be,bw=cut(b,cap)
    return combine(ae,bw,cap),combine(be,aw,cap)


def stack(bottom: Sequence[Sequence[str]], top: Sequence[Sequence[str]], cap:int)->list[list[str]]:
    b=_fixed(bottom,cap);t=_fixed(top,cap)
    work=[[EMPTY]*4 for _ in range(2*cap+1)]
    for l in range(cap):work[l]=b[l].copy()
    for l in range(cap):work[cap+1+l]=t[l].copy()
    fallen=apply_gravity(work)
    return trim(fallen[:cap])


def generate(rows: Sequence[Sequence[str]], cap:int)->list[list[str]]:
    work=_fixed(rows,cap)
    height=0
    for l,row in enumerate(work):
        if any(occupied(c) for c in row):height=l+1
    for l in range(height):
        for q in range(4):
            if work[l][q] in (EMPTY,PIN):work[l][q]=CRYSTAL
    return trim(work)


def input_full()->list[list[str]]:
    return [[ORDINARY]*4]


def one_cell_input(q:int=0)->list[list[str]]:
    # Cut SSSS to SS--, rotate so the two parts straddle the cutter, and cut
    # again.  Keep the one-cell east output, then rotate to the requested slot.
    east,_=cut(input_full(),1)
    straddled=rotate(east,1)
    one,_=cut(straddled,1)
    if sum(c!=EMPTY for r in one for c in r)!=1:
        raise AssertionError('one-cell input construction failed')
    pos=next(i for i,c in enumerate(one[0]) if c!=EMPTY)
    return rotate(one,(q-pos)%4)
