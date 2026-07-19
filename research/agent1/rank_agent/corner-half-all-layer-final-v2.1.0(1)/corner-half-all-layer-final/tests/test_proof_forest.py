from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from corner_half.half_family import is_buildable_half
from corner_half.proof_dag import (
    clear_proof_caches,
    corner_raw_proof,
    half_raw_proof,
    verify_proof,
    verify_proof_forest,
)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
HIGH_189 = (
    'PPPPPPP--S-----S---S-----S-SSS-S--S-SS---S----S-S-----S-'
    'cScScS---SScScSS-cSS-S-----S-ScS----S----cS---S-S----cS--'
    'ScS------S-cS--SS-SS---cS---S-SS----cSScSS----S--ScS----S'
    '----cPS----SP-S---S'
)


def load_columns(cap: int) -> list[str]:
    values = (REPORTS / f'columns_cap{cap}.txt').read_text().splitlines()
    return ['' if value == '<EMPTY>' else value for value in values]


def half_code(a: str, b: str, cap: int) -> str:
    return ':'.join(
        (a[l] if l < len(a) else '-')
        + (b[l] if l < len(b) else '-')
        + '--'
        for l in range(cap)
    )


def audit_corner_cap7() -> dict[str, int | float | bool]:
    values = load_columns(7)
    clear_proof_caches()
    start = perf_counter()
    roots = [corner_raw_proof(value, 7) for value in values]
    built = perf_counter() - start
    start = perf_counter()
    audit = verify_proof_forest(roots)
    verified = perf_counter() - start
    assert audit.replay_ok and audit.all_stable
    return {
        'roots': len(roots), 'build_seconds': built,
        'verify_seconds': verified, 'unique_nodes': audit.unique_nodes,
        'operation_nodes': audit.operation_nodes, 'raw_leaves': audit.raw_leaves, 'edges': audit.edges,
        'max_depth': audit.max_depth, 'replay_ok': audit.replay_ok,
    }


def audit_half_cap4() -> dict[str, int | float | bool]:
    values = load_columns(4)
    targets = []
    for left in values:
        for right in values:
            target = half_code(left, right, 4)
            if is_buildable_half(target, 4):
                targets.append(target)
    assert len(targets) == 16_193
    clear_proof_caches()
    start = perf_counter()
    roots = [half_raw_proof(target, 4) for target in targets]
    built = perf_counter() - start
    start = perf_counter()
    audit = verify_proof_forest(roots)
    verified = perf_counter() - start
    assert audit.replay_ok and audit.all_stable
    return {
        'roots': len(roots), 'build_seconds': built,
        'verify_seconds': verified, 'unique_nodes': audit.unique_nodes,
        'operation_nodes': audit.operation_nodes, 'raw_leaves': audit.raw_leaves, 'edges': audit.edges,
        'max_depth': audit.max_depth, 'replay_ok': audit.replay_ok,
    }


def audit_high_189() -> dict[str, int | float | bool]:
    clear_proof_caches()
    start = perf_counter()
    root = corner_raw_proof(HIGH_189, len(HIGH_189))
    built = perf_counter() - start
    start = perf_counter()
    audit = verify_proof(root)
    verified = perf_counter() - start
    assert audit.replay_ok and audit.all_stable
    return {
        'layers': len(HIGH_189), 'build_seconds': built,
        'verify_seconds': verified, 'unique_nodes': audit.unique_nodes,
        'operation_nodes': audit.operation_nodes, 'raw_leaves': audit.raw_leaves,
        'max_depth': audit.max_depth, 'replay_ok': audit.replay_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Run one memory-isolated raw proof-DAG audit.'
    )
    parser.add_argument(
        '--mode', choices=('corner7', 'half4', 'high189'), required=True
    )
    args = parser.parse_args()
    if args.mode == 'corner7':
        result = audit_corner_cap7()
    elif args.mode == 'half4':
        result = audit_half_cap4()
    else:
        result = audit_high_189()
    print(json.dumps(result))


if __name__ == '__main__':
    main()
