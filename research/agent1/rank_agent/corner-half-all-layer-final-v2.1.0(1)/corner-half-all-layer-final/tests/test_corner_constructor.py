from __future__ import annotations
from itertools import product
from collections import Counter

from corner_half.corner_constructor import construct_corner
from corner_half.corner_dfa import is_craftable_column


def main(max_len=10):
    total=0;kinds=Counter()
    for n in range(max_len+1):
        for chars in product('-SPc',repeat=n):
            if n and chars[-1]=='-':continue
            s=''.join(chars)
            if not is_craftable_column(s):continue
            cert=construct_corner(s,max(1,n))
            assert cert.replay_ok,cert
            total+=1;kinds[cert.kind.value]+=1
    print({'checked':total,'kinds':dict(kinds)})

if __name__=='__main__':main()
