from __future__ import annotations
from itertools import product
from collections import Counter
import random

from valid_generators import make_natural_case
from corner_half.corner_dfa import is_craftable_column
from corner_half.corner_natural_plan import compile_corner_natural
from corner_half.corner_regions import Route,analyze_column


def exhaustive(max_len=10):
 c=Counter();total=0
 for n in range(max_len+1):
  for chars in product('-SPc',repeat=n):
   s=''.join(chars)
   if s.endswith('-'):continue
   if not is_craftable_column(s):continue
   route=analyze_column(s).route
   if route is Route.EVENT:continue
   p=compile_corner_natural(s,max(1,n))
   assert p.replay_ok,p
   c[route.value]+=1;total+=1
 return {'checked':total,'routes':dict(c)}


def random_high(cases=5000,seed=20260717):
 rng=random.Random(seed)
 for _ in range(cases):
  s=make_natural_case(rng,rng.randint(7,200))
  p=compile_corner_natural(s,max(1,len(s)));assert p.replay_ok
 return {'checked':cases}

if __name__=='__main__':
 print(exhaustive())
 print(random_high(5000))
