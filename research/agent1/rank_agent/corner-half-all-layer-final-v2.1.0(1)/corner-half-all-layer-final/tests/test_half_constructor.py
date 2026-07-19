from __future__ import annotations

from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_constructor import construct_half
from corner_half.half_family import is_buildable_half


def cols(cap:int)->list[str]:
    out={''}
    for n in range(1,cap+1):
        for x in product('-SPc',repeat=n):
            if x[-1]=='-':continue
            s=''.join(x)
            if is_craftable_column(s):out.add(s)
    return sorted(out)


def hcode(a:str,b:str,cap:int)->str:
    return ':'.join(
        (a[l] if l<len(a) else '-')+(b[l] if l<len(b) else '-')+'--'
        for l in range(cap)
    )


def exhaustive(cap:int=4)->dict[str,int]:
    values=cols(cap);checked=0
    for a in values:
        for b in values:
            c=hcode(a,b,cap)
            if not is_buildable_half(c,cap):continue
            cert=construct_half(c,cap)
            assert cert.replay_ok,cert
            checked+=1
    return {'cap':cap,'columns':len(values),'checked':checked}


def random_high(cases:int=10000,seed:int=20260717)->dict[str,int]:
    rng=random.Random(seed);checked=attempts=0
    cache={}
    while checked<cases and attempts<cases*200:
        attempts+=1;cap=rng.randint(5,80)
        def one():
            while True:
                n=rng.randint(0,cap)
                if n==0:return ''
                s=''.join(rng.choice('-SPc') for _ in range(n-1))+rng.choice('SPc')
                if is_craftable_column(s):return s
        a=one();b=one();c=hcode(a,b,cap)
        if not is_buildable_half(c,cap):continue
        cert=construct_half(c,cap)
        assert cert.replay_ok,cert
        checked+=1
    return {'checked':checked,'attempts':attempts}


def main():
    print(exhaustive())
    print(random_high())

if __name__=='__main__':main()
