"""Independent transcription of the legacy ``Shape.py`` structural physics.

This intentionally follows the mutable repeated-loop algorithm rather than the
single-pass theorem kernel, so differential agreement is meaningful.
"""
from __future__ import annotations

from collections import deque
from typing import Iterable, Sequence

EMPTY, ORDINARY, PIN, CRYSTAL = "-", "S", "P", "c"
ADJ=((1,3),(0,2),(1,3),(0,2))


def trim(rows):
    out=[list(r) for r in rows]
    while out and all(x==EMPTY for x in out[-1]): out.pop()
    return out


def get(rows,l,q):
    return rows[l][q] if 0<=l<len(rows) and 0<=q<4 else EMPTY


def group(rows,l0,q0):
    start=get(rows,l0,q0)
    if start==EMPTY:return set()
    if start==PIN:return {(l0,q0)}
    crystal=start==CRYSTAL
    todo=[(l0,q0)];seen=set()
    while todo:
        l,q=todo.pop(0)
        if (l,q) in seen:continue
        cell=get(rows,l,q)
        if crystal:
            if cell!=CRYSTAL:continue
        else:
            if cell not in (ORDINARY,):continue
        seen.add((l,q))
        for nq in ADJ[q]:todo.append((l,nq))
        if crystal:
            todo.append((l-1,q));todo.append((l+1,q))
    return seen


def shatter(rows,seeds):
    total=set(seeds);todo={x for x in seeds if get(rows,*x)==CRYSTAL}
    while todo:
        pos=todo.pop()
        comp=group(rows,*pos)
        new=comp-total
        if not new:continue
        total.update(new)
        for l,q in new:
            for nl in (l-1,l+1):
                n=(nl,q)
                if get(rows,*n)==CRYSTAL and n not in total:todo.add(n)
            for nq in ADJ[q]:
                n=(l,nq)
                if get(rows,*n)==CRYSTAL and n not in total:todo.add(n)
    return total


def apply_gravity(rows:Sequence[Sequence[str]]):
    s=trim(rows)
    if not s:return []
    while True:
        supported={(0,q) for q in range(4) if get(s,0,q)!=EMPTY}
        while True:
            before=len(supported)
            visited=set()
            for l in range(len(s)):
                for q in range(4):
                    pos=(l,q)
                    if pos not in visited and get(s,l,q)!=EMPTY:
                        g=group(s,l,q)
                        if any(c in supported for c in g):supported.update(g)
                        visited.update(g)
            for l in range(len(s)):
                for q in range(4):
                    pos=(l,q);cell=get(s,l,q)
                    if pos in supported or cell==EMPTY:continue
                    if l>0 and (l-1,q) in supported:
                        supported.add(pos)
                    elif cell!=PIN:
                        for nq in ADJ[q]:
                            if (l,nq) in supported and get(s,l,nq)!=PIN:
                                supported.add(pos);break
            if len(supported)==before:break
        allcoords={(l,q) for l in range(len(s)) for q in range(4) if get(s,l,q)!=EMPTY}
        unsupported=allcoords-supported
        crystals={x for x in unsupported if get(s,*x)==CRYSTAL}
        if crystals:
            for l,q in shatter(s,crystals):
                if 0<=l<len(s):s[l][q]=EMPTY
            continue
        if not unsupported:break
        falling_groups=[];visited=set()
        for l,q in sorted(unsupported,key=lambda x:x[0]):
            if (l,q) in visited:continue
            fg=group(s,l,q)&unsupported
            if fg:
                falling_groups.append(fg);visited.update(fg)
        moved=False
        for g in falling_groups:
            d=0
            while True:
                nd=d+1;ok=True
                for l,q in g:
                    target=l-nd
                    if target<0 or (get(s,target,q)!=EMPTY and (target,q) not in g):
                        ok=False;break
                if not ok:break
                d=nd
            if d>0:
                moved=True
                pieces=sorted([(l,q,get(s,l,q)) for l,q in g],key=lambda x:-x[0])
                for l,q,_ in pieces:s[l][q]=EMPTY
                for l,q,p in pieces:s[l-d][q]=p
        if not moved:break
    return trim(s)


def push_pin(rows,cap):
    old=trim(rows)
    if not old or all(get(old,0,q)==EMPTY for q in range(4)):return old
    over=[[PIN if get(old,0,q)!=EMPTY else EMPTY for q in range(4)]]+[list(r) for r in old]
    seeds={(l,q) for l in range(cap,len(over)) for q in range(4) if get(over,l,q)!=EMPTY}
    for l,q in shatter(over,seeds):
        if 0<=l<len(over):over[l][q]=EMPTY
    return apply_gravity(over[:cap])


def code(rows):return ':'.join(''.join(r) for r in trim(rows))

def column(rows,q):
    s=''.join(get(rows,l,q) for l in range(len(rows)))
    return s.rstrip(EMPTY)
