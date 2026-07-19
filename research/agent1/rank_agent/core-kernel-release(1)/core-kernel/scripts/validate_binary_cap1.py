from __future__ import annotations
import json,time
from pathlib import Path
from shapez2_core import CompactShape
from shapez2_core import kernel as fast
from shapez2_core import reference as slow

started=time.perf_counter();states=[CompactShape(bits,1) for bits in range(256)];pairs=0
for a in states:
    for b in states:
        assert fast.stack(a,b)==slow.stack(a,b)
        assert fast.swap(a,b,0)==slow.swap(a,b,0)
        assert fast.swap(a,b,1)==slow.swap(a,b,1)
        assert fast.stack_compact_equivalent(a,b)==fast.stack(a,b)
        pairs+=1
report={'status':'PASS','cap':1,'ordered_pairs':pairs,'checks':['stack','vertical_swap','horizontal_swap','compact_stack_equivalence'],'elapsed_seconds':time.perf_counter()-started}
Path('reports/validation_binary_cap1.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
