from __future__ import annotations
import random

from corner_half.corner_constructor import construct_corner
from test_corner_event_generated import make_case


def main(cases:int=2000,seed:int=913):
    rng=random.Random(seed)
    for i in range(cases):
        s=make_case(rng,rng.randint(7,200))
        cert=construct_corner(s,len(s))
        assert cert.replay_ok,(i,s,cert)
    print({'checked':cases})

if __name__=='__main__':main()
