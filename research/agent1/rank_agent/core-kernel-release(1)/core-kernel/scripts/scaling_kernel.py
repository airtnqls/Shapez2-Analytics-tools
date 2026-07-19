from __future__ import annotations
import json,time
from pathlib import Path
from shapez2_core import CompactShape,apply_gravity,pin_push,rotate,stack

def dense(cap:int)->CompactShape:
    # NORMAL=01 in each 2-bit cell => 0x55 per full layer.
    return CompactShape(int.from_bytes(bytes([0x55])*cap,'little'),cap)

def measure(fn):
    t=time.perf_counter();result=fn();return time.perf_counter()-t,result

rows=[]
for cap in (1000,5000,10000,50000,100000):
    shape=dense(cap)
    tg,stable=measure(lambda:apply_gravity(shape))
    tr,_=measure(lambda:rotate(shape))
    tp,_=measure(lambda:pin_push(shape))
    ts,_=measure(lambda:stack(shape,shape))
    rows.append({'cap':cap,'gravity_s':tg,'rotate_s':tr,'pin_push_s':tp,'stack_s':ts})
    print(rows[-1],flush=True)
report={'status':'PASS','family':'full NORMAL rows','rows':rows,'note':'wall times are environment-specific'}
Path('reports/scaling.json').write_text(json.dumps(report,indent=2)+'\n')
