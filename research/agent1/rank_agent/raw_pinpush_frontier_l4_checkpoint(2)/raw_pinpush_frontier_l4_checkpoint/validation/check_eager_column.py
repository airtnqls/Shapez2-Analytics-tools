from pathlib import Path
from collections import Counter
import argparse
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from provenance_sim import parse

parser = argparse.ArgumentParser()
parser.add_argument('--targets', type=Path, required=True)
parser.add_argument('--predecessors', type=Path, required=True)
args = parser.parse_args()

ts=args.targets.read_text(encoding='utf-8').splitlines()[:40171]
ps=args.predecessors.read_text(encoding='utf-8').splitlines()[:40171]
bad=[]; zero_masks=Counter(); min_def=Counter(); pertarget=Counter()
for i,(t,p) in enumerate(zip(ts,ps)):
 tr=[''.join('-' if x is None else x.k for x in row) for row in parse(t,5)];tr+=['----']*(5-len(tr))
 pr=parse(p,5);pr += [[None]*4 for _ in range(5-len(pr))]
 bm=sum(1<<q for q,x in enumerate(pr[0]) if x is not None)
 seq=[[] for _ in range(4)]
 ok=True
 for q in range(4):
  for r in range(5):
   if tr[r][q] in 'SP':seq[q].append((r,tr[r][q]))
  if bm>>q&1:
   if not seq[q] or seq[q][0]!=(0,'P'):ok=False
   else:seq[q]=seq[q][1:]
 if not ok:continue
 c=[0]*4; localbad=False
 for s in range(4):
  for q in range(4):
   x=pr[s][q]
   if x is not None and x.k in 'SP':c[q]+=1
  E=[sum(r<=s+1 for r,k in seq[q]) for q in range(4)]
  ds=[E[q]-c[q] for q in range(4)]
  m=sum((ds[q]==0)<<q for q in range(4))
  zero_masks[m]+=1;min_def[min(ds)]+=1
  if not m:
   bad.append((i,s,t,p,ds,E,c));localbad=True
 if localbad:pertarget['bad']+=1
 else:pertarget['ok']+=1
print('bad states',len(bad),'targets',pertarget)
print('zero masks',dict(zero_masks))
print('min deficit',dict(min_def))
print('examples',bad[:10])
