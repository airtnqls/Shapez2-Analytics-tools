from __future__ import annotations

import random

from corner_half.c7_gadget import C7Duty, DutyKind, compile_c7
from corner_half.structural_physics import parse, column
from corner_half.legacy_structural_oracle import apply_gravity as legacy_gravity, push_pin as legacy_push, code as legacy_code, column as legacy_column


def make_case(rng: random.Random, cap: int, count: int, floor: bool):
    a = ['-'] * cap
    duties=[]
    cursor=0
    if floor:
        a[0]='-'
        a[1]='-'  # empty pre-push bottom => empty A receipt
        source=rng.randint(3, min(cap-3, 6))
        for l in range(2, source):
            a[l]=rng.choice(['c','c','-'])
        if all(a[l] != 'c' for l in range(2,source)):
            a[source-1]='c'
        a[source]='S'
        if source + 1 < cap:
            a[source + 1] = 'c'
        duties.append(C7Duty(source,0,DutyKind.FLOOR))
        cursor=source
        count-=1
    else:
        a[0]='P'
        a[1]=rng.choice(['S','c'])
        cursor=1

    for _ in range(count):
        # a static layer for an upper unit anchor (the first unit is grounded)
        if duties:
            anchor=cursor+1
            if anchor >= cap-5: break
            a[anchor]=rng.choice(['S','c'])
        else:
            anchor=cursor
        target=anchor+2
        if target+2 >= cap: break
        a[target-1]='-'
        source=rng.randint(target+1, min(cap-2,target+5))
        for l in range(target,source):
            a[l]=rng.choice(['c','c','-'])
        if all(a[l] != 'c' for l in range(target,source)):
            a[source-1]='c'
        a[source]='S'
        duties.append(C7Duty(source,target,DutyKind.ANCHORED))
        cursor=source

    # Add a separated top keeper so B/C heights and kept crystals are exercised.
    if cursor+1 < cap:
        a[cursor+1]=rng.choice(['S','c'])
    return ''.join(a).rstrip('-'), duties


def main():
    rng=random.Random(20260717)
    checked=0
    for cap in range(6,41):
        for _ in range(300):
            count=rng.randint(1, min(6, max(1,(cap-2)//4)))
            floor=rng.random()<0.35
            a,duties=make_case(rng,cap,count,floor)
            if not duties:
                continue
            cert=compile_c7(a,cap,duties)
            assert cert.stable_predecessor, cert
            assert cert.replay_ok, cert
            pred=parse(cert.predecessor)
            assert legacy_code(legacy_gravity(pred)) == cert.predecessor, cert
            legacy_out=legacy_push(pred,cap)
            assert legacy_column(legacy_out,0) == cert.expected_a, cert
            checked+=1
    print({'checked':checked})


if __name__=='__main__':
    main()
