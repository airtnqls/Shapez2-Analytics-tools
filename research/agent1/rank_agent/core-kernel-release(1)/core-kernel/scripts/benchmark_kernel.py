"""Reproducible packed-kernel vs independent-reference benchmark."""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from pathlib import Path

from shapez2_core import CompactShape
from shapez2_core import kernel as fast
from shapez2_core import reference as slow


def _median_time(fn, values):
    samples=[]
    for value in values:
        t=time.perf_counter(); fn(value); samples.append(time.perf_counter()-t)
    return statistics.median(samples), sum(samples)


def run(seed: int) -> dict:
    rng=random.Random(seed)
    rows=[]
    plan=((5,1000),(20,500),(50,200),(100,100),(200,40))
    for cap,cases in plan:
        raw=[CompactShape(rng.randrange(1<<(8*cap)),cap) for _ in range(cases)]
        stable=[fast.apply_gravity(value) for value in raw]
        pairs=list(zip(stable[0::2],stable[1::2]))

        fg,fg_total=_median_time(fast.apply_gravity,raw)
        sg,sg_total=_median_time(slow.apply_gravity,raw)
        fp,fp_total=_median_time(fast.pin_push,stable)
        sp,sp_total=_median_time(slow.pin_push,stable)
        fs,fs_total=_median_time(lambda pair:fast.stack(*pair),pairs)
        ss,ss_total=_median_time(lambda pair:slow.stack(*pair),pairs)
        fc,fc_total=_median_time(lambda value:fast.cut(value,0),stable)
        sc,sc_total=_median_time(lambda value:slow.cut(value,0),stable)
        rows.append({
            'cap':cap,'raw_cases':cases,'binary_cases':len(pairs),
            'gravity':{'fast_median_us':fg*1e6,'reference_median_us':sg*1e6,'speedup':sg/fg if fg else None,'fast_total_s':fg_total,'reference_total_s':sg_total},
            'pin_push':{'fast_median_us':fp*1e6,'reference_median_us':sp*1e6,'speedup':sp/fp if fp else None,'fast_total_s':fp_total,'reference_total_s':sp_total},
            'stack':{'fast_median_us':fs*1e6,'reference_median_us':ss*1e6,'speedup':ss/fs if fs else None,'fast_total_s':fs_total,'reference_total_s':ss_total},
            'cut':{'fast_median_us':fc*1e6,'reference_median_us':sc*1e6,'speedup':sc/fc if fc else None,'fast_total_s':fc_total,'reference_total_s':sc_total},
        })
        print('cap',cap,'done',flush=True)
    return {'seed':seed,'python':'3.13.5','note':'microbenchmarks are environment-specific; reference is deliberately simple','rows':rows}


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=20260717);p.add_argument('--output',type=Path);a=p.parse_args()
    report=run(a.seed);text=json.dumps(report,indent=2);print(text)
    if a.output:a.output.write_text(text+'\n')

if __name__=='__main__':main()
