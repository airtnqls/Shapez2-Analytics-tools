from __future__ import annotations
from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_ir import compile_corner_ir
from test_corner_event_generated import make_case


def main():
    checked=0
    for n in range(10):
        for chars in product('-SPc',repeat=n):
            if n and chars[-1]=='-':continue
            s=''.join(chars)
            if not is_craftable_column(s):continue
            p=compile_corner_ir(s,max(1,n))
            assert p.replay_ok,p
            checked+=1
    rng=random.Random(20260717)
    for _ in range(1000):
        s=make_case(rng,rng.randint(7,200))
        assert compile_corner_ir(s,len(s)).replay_ok
    print({'exhaustive':checked,'event_high':1000})

if __name__=='__main__':main()
