from __future__ import annotations
from itertools import product
import random

from corner_half.corner_constructor import construct_corner
from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_macro_replay import replay_corner_certificate
from test_corner_event_generated import make_case


def exhaustive(max_len:int=6):
    checked=0;steps=0
    for n in range(max_len+1):
        for x in product('-SPc',repeat=n):
            if n and x[-1]=='-':continue
            s=''.join(x)
            if not is_craftable_column(s):continue
            cert=construct_corner(s,max(1,n))
            replay=replay_corner_certificate(cert)
            assert replay.replay_ok,(s,cert,replay)
            checked+=1;steps+=len(replay.steps)
    return {'checked':checked,'macro_steps':steps}


def high_event(cases:int=100,seed:int=991):
    rng=random.Random(seed);steps=0
    for _ in range(cases):
        s=make_case(rng,rng.randint(7,150))
        replay=replay_corner_certificate(construct_corner(s,len(s)))
        assert replay.replay_ok,(s,replay)
        steps+=len(replay.steps)
    return {'checked':cases,'macro_steps':steps}


def main():
    print(exhaustive())
    print(high_event())
if __name__=='__main__':main()
