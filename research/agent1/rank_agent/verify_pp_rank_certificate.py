from __future__ import annotations
import json
from pathlib import Path
from typing import Any

PIN = 2


def receipt_rank_rows(rows: list[list[int]]) -> int:
    cap=len(rows)
    total=0
    for q in range(4):
        l=0
        while l<cap and rows[l][q]==PIN:
            total+=1;l+=1
    return total


def verify_record(rec: dict[str, Any]) -> None:
    tr=receipt_rank_rows(rec['target_rows'])
    pr=receipt_rank_rows(rec['pre_push_rows'])
    br=receipt_rank_rows(rec['recursive_base_rows'])
    assert tr==rec['sigma_target']
    assert pr==rec['sigma_pre_push']
    assert br==rec['sigma_base']
    assert br < tr, (br,tr)
    assert rec['pin_push_replay'] is True
    assert rec['stack_replay'] is True


def main(path: str) -> None:
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    records=data if isinstance(data,list) else data['records']
    for rec in records: verify_record(rec)
    print(f'valid={len(records)}')

if __name__=='__main__':
    import sys
    if len(sys.argv)!=2: raise SystemExit('usage: verify_pp_rank_certificate.py CERT.json')
    main(sys.argv[1])
