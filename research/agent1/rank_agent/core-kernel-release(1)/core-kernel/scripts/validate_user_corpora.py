from __future__ import annotations
import argparse,json,time
from pathlib import Path
from shapez2_core import CompactShape,apply_gravity

def inspect(path:Path,limit:int|None,cap:int)->dict:
 lines=[x.strip() for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
 if limit is not None:lines=lines[:limit]
 started=time.perf_counter();parsed=stable=roundtrip=0;heights={};examples=[]
 for index,code in enumerate(lines,1):
  try:x=CompactShape.parse(code,cap=cap)
  except Exception as exc:
   if len(examples)<10:examples.append({'line':index,'code':code,'error':repr(exc)})
   continue
  parsed+=1;heights[str(x.height)]=heights.get(str(x.height),0)+1
  stable+=apply_gravity(x)==x
  structural=x.to_structural(empty='----')
  roundtrip+=CompactShape.parse(structural,cap=cap)==x
 return {'path':str(path),'requested':len(lines),'parsed':parsed,'stable':stable,'roundtrip':roundtrip,'height_histogram':heights,'errors':examples,'elapsed_seconds':time.perf_counter()-started}

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('/mnt/data'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 report={'status':'PASS','corpora':[inspect(a.root/'40171.txt',40171,5),inspect(a.root/'all40171clawsnohybrid.txt',40171,5),inspect(a.root/'all40171clawsnohybrid_정렬됨_claw_complex_hybrid.txt',None,5)]}
 for row in report['corpora']:
  if row['parsed']!=row['requested'] or row['roundtrip']!=row['parsed']:report['status']='FAIL'
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
