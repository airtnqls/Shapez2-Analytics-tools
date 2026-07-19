from __future__ import annotations
import json, random, sys, time
from pathlib import Path
ROOT=Path('/mnt/data/rank_agent/core-kernel-release(1)/core-kernel/src')
sys.path.insert(0,str(ROOT))
from shapez2_core import CompactShape, pin_push, stack, rotate, mirror, PIN, EMPTY, is_stable


def runs(s: CompactShape):
    out=[]
    for q in range(4):
        k=0
        while k<s.cap and s.cell(k,q)==PIN:
            k+=1
        out.append(k)
    return tuple(out)

def sigma(s): return sum(runs(s))

def pure_full_pin_columns(s: CompactShape) -> bool:
    # Each column is either empty at all layers or PIN at every cap layer.
    any_occ=False
    for q in range(4):
        vals=[s.cell(l,q) for l in range(s.cap)]
        if all(v==EMPTY for v in vals):
            continue
        any_occ=True
        if not all(v==PIN for v in vals):
            return False
    return any_occ

def check_pin(cap:int, exhaustive=False, samples=0):
    limit=1<<(8*cap)
    it=range(limit) if exhaustive else (random.randrange(limit) for _ in range(samples))
    checked=stable=nondeg=0; worst=999; min_nondeg=999; failures=[]; equality=[]; t=time.perf_counter()
    for bits in it:
        s=CompactShape(bits,cap)
        checked+=1
        if s.is_empty or not is_stable(s): continue
        stable+=1
        y=pin_push(s); gap=sigma(y)-sigma(s); worst=min(worst,gap)
        if pure_full_pin_columns(s):
            if gap!=0: failures.append(('degenerate-gap',s.to_structural(),y.to_structural(),runs(s),runs(y),gap))
            continue
        nondeg+=1
        min_nondeg=min(min_nondeg,gap)
        if gap<1:
            failures.append(('strict-fail',s.to_structural(),y.to_structural(),runs(s),runs(y),gap))
            if len(failures)>=20: break
        if gap==0 and len(equality)<10: equality.append((s.to_structural(),y.to_structural()))
    return {'cap':cap,'checked':checked,'stable':stable,'nondegenerate':nondeg,'minimum_nondegenerate_gap':min_nondeg if nondeg else None,'minimum_all_stable_gap':worst,'failures':failures,'seconds':time.perf_counter()-t}

def check_stack(cap:int, exhaustive=False, samples=0):
    limit=1<<(8*cap)
    pairs=((a,b) for a in range(limit) for b in range(limit)) if exhaustive else ((random.randrange(limit),random.randrange(limit)) for _ in range(samples))
    checked=0; stable_bottoms=0; worst=999; failures=[]; t=time.perf_counter()
    for a,b in pairs:
        bottom=CompactShape(a,cap); top=CompactShape(b,cap); checked+=1
        if not is_stable(bottom) or not is_stable(top): continue
        stable_bottoms+=1
        out=stack(bottom,top); gap=sigma(out)-sigma(bottom); worst=min(worst,gap)
        if gap<0:
            failures.append((bottom.to_structural(),top.to_structural(),out.to_structural(),runs(bottom),runs(out),gap)); break
    return {'cap':cap,'checked':checked,'stable_pairs':stable_bottoms,'worst_gap':worst,'failures':failures,'seconds':time.perf_counter()-t}

def check_sym(cap:int, exhaustive=False,samples=0):
    limit=1<<(8*cap)
    it=range(limit) if exhaustive else (random.randrange(limit) for _ in range(samples))
    checked=0; failures=[]; t=time.perf_counter()
    for bits in it:
        s=CompactShape(bits,cap); v=sigma(s)
        vals=[sigma(rotate(s,k)) for k in range(4)]+[sigma(mirror(s))]
        checked+=1
        if any(x!=v for x in vals): failures.append((s.to_structural(),v,vals));break
    return {'cap':cap,'checked':checked,'failures':failures,'seconds':time.perf_counter()-t}

random.seed(20260718)
report={
 'measure':'sigma(X)=sum over columns of bottom-consecutive PIN run lengths',
 'claim':'for every stable, nonempty, non-pure-full-pin-column X, sigma(pin_push(X)) >= sigma(X)+1; stack and D4 do not decrease sigma',
 'pin':[check_pin(1,True),check_pin(2,True),check_pin(3,False,200_000)],
 'stack':[check_stack(1,True),check_stack(2,False,100_000),check_stack(3,False,50_000)],
 'symmetry':[check_sym(1,True),check_sym(2,True),check_sym(3,False,100_000)]
}
out=Path('/mnt/data/rank_agent/PIN_RECEIPT_RANK_VALIDATION.json');out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
