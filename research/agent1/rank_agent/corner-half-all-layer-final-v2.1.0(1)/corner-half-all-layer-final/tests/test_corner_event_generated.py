from __future__ import annotations
import random
from collections import Counter

from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_event_plan import compile_corner_event
from corner_half.corner_regions import Route, analyze_column, is_i_weak, is_z_evt


def gen_zone(rng: random.Random, max_len: int) -> str:
    if rng.random() < .5:
        a=rng.randint(1,max(1,min(8,max_len)))
        remaining=max_len-a
        if remaining<=0 or rng.random()<.15:return 'P'*a
        n=rng.randint(1,remaining)
        body=['-' if rng.random()<.65 else 'S' for _ in range(n)]
        if 'S' not in body:body[rng.randrange(n)]='S'
        return 'P'*a+''.join(body)
    n=rng.randint(3,max(3,max_len))
    while True:
        body=['-' if rng.random()<.65 else 'S' for _ in range(n)]
        if body.count('-')>=2 and 'S' in body:return ''.join(body)


def gen_iweak(rng: random.Random, n: int) -> str:
    if n==0:return ''
    if n==1:return 'S'
    s=['-' if rng.random()<.7 else 'S' for _ in range(n)]
    s[0]='S'
    if s.count('S')<2:s[rng.randrange(1,n)]='S'
    return ''.join(s)


def gen_top(rng: random.Random,n:int)->str:
    out=[]
    for _ in range(n):
        choices=['-','S','P']
        if out and out[-1]=='-':choices=['-','S']
        out.append(rng.choice(choices))
    while out and out[-1]=='-':out.pop()
    return ''.join(out)


def make_case(rng: random.Random,max_len=200)->str:
    for _ in range(1000):
        zone=gen_zone(rng,max(3,max_len//3))
        remaining=max_len-len(zone)-1
        if remaining<0:continue
        m=rng.randint(0,min(20,max(0,remaining//2)))
        segments=[]
        for _ in range(m):
            if remaining<=1:break
            n=rng.randint(0,min(12,remaining-1))
            segments.append(gen_iweak(rng,n));remaining-=n+1
        top=gen_top(rng,rng.randint(0,max(0,min(20,remaining))))
        s=zone+'c'+''.join(seg+'c' for seg in segments)+top
        if len(s)<=max_len and is_craftable_column(s) and analyze_column(s).route is Route.EVENT:
            return s
    raise RuntimeError('generator failed')


def main(cases=10000,seed=20260717):
    rng=random.Random(seed);dist=Counter();max_len=max_d=0
    for _ in range(cases):
        s=make_case(rng,rng.randint(7,200))
        p=compile_corner_event(s,len(s))
        assert p.replay_ok,p
        dist[len(p.duties)]+=1;max_d=max(max_d,len(p.duties));max_len=max(max_len,len(s))
    print({'checked':cases,'max_len':max_len,'max_duties':max_d,'duty_distribution':dict(dist)})

if __name__=='__main__':main()
