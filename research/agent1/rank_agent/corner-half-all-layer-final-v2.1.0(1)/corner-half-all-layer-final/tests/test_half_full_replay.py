from __future__ import annotations
from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_family import is_buildable_half
from corner_half.half_full_replay import replay_half_full


def columns(cap:int):
    out={''}
    for n in range(1,cap+1):
        for chars in product('-SPc',repeat=n):
            s=''.join(chars).rstrip('-')
            if is_craftable_column(s):out.add(s)
    return sorted(out)


def half_code(a,b,cap):
    return ':'.join((a[l] if l<len(a) else '-')+(b[l] if l<len(b) else '-')+'--' for l in range(cap))


def main():
    total=0
    for cap in range(1,4):
        vals=columns(cap);cnt=0
        for a in vals:
            for b in vals:
                x=half_code(a,b,cap)
                if not is_buildable_half(x,cap):continue
                r=replay_half_full(x,cap);assert r.replay_ok,r
                cnt+=1
        total+=cnt;print({'cap':cap,'checked':cnt})
    rng=random.Random(20260717)
    for cap in (4,5,7,12,20,50):
        vals=columns(min(cap,7));got=attempts=0
        while got<50 and attempts<100000:
            attempts+=1;a=rng.choice(vals);b=rng.choice(vals);x=half_code(a,b,cap)
            if not is_buildable_half(x,cap):continue
            assert replay_half_full(x,cap).replay_ok;got+=1
        assert got==50
        print({'cap':cap,'sampled':got})
    print({'exhaustive_total':total})

if __name__=='__main__':main()
