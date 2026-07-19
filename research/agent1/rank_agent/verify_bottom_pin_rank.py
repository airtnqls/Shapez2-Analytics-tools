from __future__ import annotations
import json, random, sys, time
from pathlib import Path
ROOT=Path('/mnt/data/rank_agent/core-kernel-release(1)/core-kernel/src')
sys.path.insert(0,str(ROOT))
from shapez2_core import CompactShape, pin_push, stack, rotate, mirror, PIN


def rho(s: CompactShape) -> int:
    best=0
    for q in range(4):
        k=0
        while k<s.cap and s.cell(k,q)==PIN:
            k+=1
        best=max(best,k)
    return best

def check_pin(cap:int, exhaustive:bool, samples:int=0):
    limit=1<<(8*cap)
    it=range(limit) if exhaustive else (random.randrange(limit) for _ in range(samples))
    checked=0
    worst_gap=999
    examples=[]
    t=time.perf_counter()
    for bits in it:
        s=CompactShape(bits,cap)
        if s.is_empty: continue
        y=pin_push(s)
        gap=rho(y)-rho(s)
        worst_gap=min(worst_gap,gap)
        if gap<1:
            examples.append((s.to_structural(),y.to_structural(),rho(s),rho(y)))
            if len(examples)>=10: break
        checked+=1
    return {'cap':cap,'checked':checked,'worst_gap':worst_gap,'failures':examples,'seconds':time.perf_counter()-t}

def check_rotation(cap:int, exhaustive:bool, samples:int=0):
    limit=1<<(8*cap)
    it=range(limit) if exhaustive else (random.randrange(limit) for _ in range(samples))
    checked=0; failures=[]; t=time.perf_counter()
    for bits in it:
        s=CompactShape(bits,cap)
        base=rho(s)
        vals=[rho(rotate(s,k)) for k in range(4)]+[rho(mirror(s))]
        if any(v!=base for v in vals):
            failures.append((s.to_structural(),base,vals)); break
        checked+=1
    return {'cap':cap,'checked':checked,'failures':failures,'seconds':time.perf_counter()-t}

def check_stack(cap:int, exhaustive:bool, samples:int=0):
    limit=1<<(8*cap)
    if exhaustive:
        pairs=((a,b) for a in range(limit) for b in range(limit))
    else:
        pairs=((random.randrange(limit),random.randrange(limit)) for _ in range(samples))
    checked=0; worst_gap=999; failures=[]; t=time.perf_counter()
    for a,b in pairs:
        bottom=CompactShape(a,cap); top=CompactShape(b,cap)
        out=stack(bottom,top)
        gap=rho(out)-rho(bottom)
        worst_gap=min(worst_gap,gap)
        if gap<0:
            failures.append((bottom.to_structural(),top.to_structural(),out.to_structural(),rho(bottom),rho(out)))
            if len(failures)>=10: break
        checked+=1
    return {'cap':cap,'checked':checked,'worst_gap':worst_gap,'failures':failures,'seconds':time.perf_counter()-t}

random.seed(20260718)
report={
 'theorem':'rho(PinPush(X)) >= rho(X)+1 for nonempty X; rho(Stack(B,T)) >= rho(B); rho invariant under D4',
 'rho':'maximum, over four columns, of consecutive PIN cells from layer 0',
 'pin':[check_pin(1,True),check_pin(2,True),check_pin(3,False,1_000_000)],
 'symmetry':[check_rotation(1,True),check_rotation(2,True),check_rotation(3,False,250_000)],
 'stack':[check_stack(1,True),check_stack(2,False,500_000),check_stack(3,False,250_000)],
}
Path('/mnt/data/rank_agent/BOTTOM_PIN_RANK_VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
