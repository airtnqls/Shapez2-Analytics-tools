from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from collections import deque

@dataclass
class C:
    k:str
    origin:object=None

def parse(code,L=5):
    rows=[]
    for r in code.split(':') if code else []:
        if len(r)>=8:r=''.join(r[2*q] for q in range(4))
        r=(r+'----')[:4]
        rows.append([None if x=='-' else C(x) for x in r])
    return rows

def code(g):
    rows=[''.join('-' if x is None else x.k for x in r) for r in g]
    while rows and rows[-1]=='----':rows.pop()
    return ':'.join(rows)

def adj(q):return ((q-1)&3,(q+1)&3)
def get(g,r,q):return g[r][q] if 0<=r<len(g) else None

def hgroup(g,r,q,crystal=None):
    c=get(g,r,q)
    if c is None:return set()
    if c.k=='P':return {(r,q)}
    if crystal is None:crystal=c.k=='c'
    todo=[(r,q)];seen=set()
    while todo:
        a=todo.pop()
        if a in seen:continue
        rr,qq=a;x=get(g,rr,qq)
        if x is None:continue
        if crystal and x.k!='c':continue
        if not crystal and x.k in ('c','P'):continue
        seen.add(a)
        for nq in adj(qq):todo.append((rr,nq))
        if crystal:
            todo.append((rr-1,qq));todo.append((rr+1,qq))
    return seen

def support(g):
    sup={(0,q) for q in range(4) if get(g,0,q) is not None}
    changed=True
    while changed:
        changed=False
        # vertical upward
        for r in range(1,len(g)):
            for q in range(4):
                if get(g,r,q) is not None and (r-1,q) in sup and (r,q) not in sup:
                    sup.add((r,q));changed=True
        # horizontal non-pin
        for r in range(len(g)):
            for q in range(4):
                x=get(g,r,q)
                if x is None or x.k=='P' or (r,q) in sup:continue
                if any((r,nq) in sup and get(g,r,nq) is not None and get(g,r,nq).k!='P' for nq in adj(q)):
                    sup.add((r,q));changed=True
        # crystal hanging downward
        for r in range(len(g)-1):
            for q in range(4):
                if get(g,r,q) is not None and get(g,r,q).k=='c' and get(g,r+1,q) is not None and get(g,r+1,q).k=='c' and (r+1,q) in sup and (r,q) not in sup:
                    sup.add((r,q));changed=True
    return sup

def shatter_component(g,seeds):
    out=set();todo=list(seeds)
    while todo:
        r,q=todo.pop()
        if (r,q) in out:continue
        x=get(g,r,q)
        if x is None:continue
        out.add((r,q))
        if x.k=='c':
            for nq in adj(q):
                if get(g,r,nq) is not None and get(g,r,nq).k=='c':todo.append((r,nq))
            for rr in (r-1,r+1):
                if get(g,rr,q) is not None and get(g,rr,q).k=='c':todo.append((rr,q))
    return out

def gravity(g):
    while True:
        sup=support(g)
        uns={(r,q) for r in range(len(g)) for q in range(4) if get(g,r,q) is not None and (r,q) not in sup}
        uc={x for x in uns if get(g,*x).k=='c'}
        if uc:
            for r,q in shatter_component(g,uc):g[r][q]=None
            continue
        if not uns:break
        # bottom-up current groups, recompute membership as moving
        moved=False;visited=set()
        for r in range(len(g)):
            for q in range(4):
                if (r,q) not in uns or (r,q) in visited or get(g,r,q) is None:continue
                grp=hgroup(g,r,q)&uns
                visited|=grp
                d=0
                while True:
                    nd=d+1;ok=True
                    for rr,qq in grp:
                        tr=rr-nd
                        if tr<0:ok=False;break
                        if get(g,tr,qq) is not None and (tr,qq) not in grp:
                            ok=False;break
                    if not ok:break
                    d=nd
                if d:
                    vals=[(rr,qq,g[rr][qq]) for rr,qq in grp]
                    for rr,qq,_ in vals:g[rr][qq]=None
                    for rr,qq,x in vals:g[rr-d][qq]=x
                    moved=True
        if not moved:break
    while g and all(x is None for x in g[-1]):g.pop()
    return g

def push(pre,cap=5):
    src=parse(pre,cap)
    for r,row in enumerate(src):
        for q,x in enumerate(row):
            if x:x.origin=(r,q)
    if not src:return []
    bottom=src[0] if src else [None]*4
    g=[[C('P',None) if bottom[q] is not None else None for q in range(4)]]+[list(r) for r in src]
    # destroy overflow indices >=cap and crystal propagation
    seeds={(r,q) for r in range(cap,len(g)) for q in range(4) if get(g,r,q) is not None}
    for r,q in shatter_component(g,seeds):g[r][q]=None
    g=g[:cap]
    return gravity(g)

if __name__=='__main__':
    ts=Path('/mnt/data/all40171clawsnohybrid.txt').read_text().splitlines()[:40171]
    ps=Path('/mnt/data/original_predecessors_40171.txt').read_text().splitlines()[:40171]
    bad=[]
    for i,(t,p) in enumerate(zip(ts,ps)):
        got=code(push(p,5))
        if got!=t:
            bad.append((i,t,p,got))
            if len(bad)>=20:break
    print('bad',len(bad));print(*bad[:3],sep='\n')
