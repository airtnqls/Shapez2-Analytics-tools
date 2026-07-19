from __future__ import annotations
from itertools import product
import random
from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_full_replay import replay_corner_full
from test_corner_event_generated import make_case


def main():
    checked=0
    for n in range(8):
        for chars in product('-SPc',repeat=n):
            if n and chars[-1]=='-':continue
            s=''.join(chars)
            if not is_craftable_column(s):continue
            r=replay_corner_full(s,max(1,n))
            assert r.replay_ok,r
            checked+=1
    rng=random.Random(20260717)
    for _ in range(25):
        s=make_case(rng,rng.randint(7,60))
        r=replay_corner_full(s,len(s));assert r.replay_ok,r
    print({'exhaustive':checked,'event_high':25})

if __name__=='__main__':main()
