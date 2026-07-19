from __future__ import annotations
import hashlib,random
from corner_half.corner_constructor import construct_corner
from corner_half.half_constructor import construct_half
from corner_half.half_family import is_buildable_half
from test_corner_event_generated import make_case

rng=random.Random(77);items=[]
for _ in range(1000):
    s=make_case(rng,rng.randint(7,100))
    a=construct_corner(s,len(s));b=construct_corner(s,len(s))
    assert a==b
    items.append(repr(a))
# deterministic random stable half sample from constructed event predecessors' BC halves
checked=0
for _ in range(5000):
    if checked>=1000:break
    s=make_case(rng,rng.randint(7,80));c=construct_corner(s,len(s))
    if not c.event:continue
    _,bcol,ccol,_=c.event.c7.predecessor_columns
    cap=len(s)
    code=':'.join((bcol[l] if l<len(bcol) else '-')+(ccol[l] if l<len(ccol) else '-')+'--' for l in range(cap))
    if not is_buildable_half(code,cap):continue
    x=construct_half(code,cap);y=construct_half(code,cap);assert x==y
    items.append(repr(x));checked+=1
h=hashlib.sha256('\n'.join(items).encode()).hexdigest()
print({'corner':1000,'half':checked,'sha256':h})
