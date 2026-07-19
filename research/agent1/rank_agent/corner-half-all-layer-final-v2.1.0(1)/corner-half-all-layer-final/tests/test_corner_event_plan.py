from __future__ import annotations

from collections import Counter
from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_event_plan import compile_corner_event
from corner_half.corner_regions import Route, analyze_column
from test_corner_event_generated import make_case


def exhaustive(max_len: int = 9):
    checked=0; duties=Counter()
    for n in range(1,max_len+1):
        for chars in product('-SPc', repeat=n):
            if chars[-1]=='-':continue
            s=''.join(chars)
            if not is_craftable_column(s):continue
            w=analyze_column(s)
            if w.route is not Route.EVENT:continue
            p=compile_corner_event(s,n)
            assert p.replay_ok,p
            checked+=1;duties[len(p.duties)]+=1
    return {'checked':checked,'duties':dict(duties)}


def generated_high(cases:int=5000,seed:int=20260717):
    rng=random.Random(seed);max_d=0;max_len=0
    for _ in range(cases):
        s=make_case(rng,rng.randint(7,200))
        p=compile_corner_event(s,len(s))
        assert p.replay_ok,p
        max_d=max(max_d,len(p.duties));max_len=max(max_len,len(s))
    return {'checked':cases,'max_len':max_len,'max_duties':max_d}


def main():
    print(exhaustive())
    print(generated_high())

if __name__=='__main__':main()
