from __future__ import annotations
from itertools import product

from corner_half.structural_physics import apply_gravity,code,is_stable,parse
from corner_half.structural_ops import cut,generate,input_full,one_cell_input,rotate,stack,swap


def main():
    assert code(input_full())=='SSSS'
    for q in range(4):
        x=one_cell_input(q);assert code(x)==''.join('S' if i==q else '-' for i in range(4))
    checked=0
    # Algebraic sanity at cap 2 over every stable one-layer pair.
    vals=[]
    for row in product('-SPc',repeat=4):
        x=apply_gravity([row])
        if is_stable(x):vals.append(x)
    for a in vals:
        ae,aw=cut(a,2)
        assert is_stable(ae) and is_stable(aw)
        assert code(rotate(rotate(rotate(rotate(a)))))==code(a)
        for b in vals:
            x,y=swap(a,b,2);assert is_stable(x) and is_stable(y)
            z=stack(a,b,2);assert is_stable(z)
            g=generate(a,2);assert is_stable(g)
            checked+=1
    print({'rows':len(vals),'pairs':checked})

if __name__=='__main__':main()
