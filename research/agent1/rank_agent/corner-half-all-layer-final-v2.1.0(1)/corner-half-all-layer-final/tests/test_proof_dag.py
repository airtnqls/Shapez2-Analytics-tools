from __future__ import annotations

from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_family import is_buildable_half
from corner_half.proof_dag import (
    clear_proof_caches,
    corner_raw_proof,
    half_raw_proof,
    one_pin_proof,
    single_layer_s_pattern_proof,
    verify_proof,
)
from test_corner_event_generated import make_case


def half_code(a: str, b: str, cap: int) -> str:
    return ':'.join(
        (a[l] if l < len(a) else '-') + (b[l] if l < len(b) else '-') + '--'
        for l in range(cap)
    )


def columns(cap: int) -> list[str]:
    out = {''}
    for n in range(1, cap + 1):
        for chars in product('-SPc', repeat=n):
            if chars[-1] == '-':
                continue
            s = ''.join(chars)
            if is_craftable_column(s):
                out.add(s)
    return sorted(out)


def main() -> None:
    for cap in range(1, 8):
        for q in range(4):
            assert verify_proof(one_pin_proof(cap, q)).replay_ok
        for mask in range(16):
            assert verify_proof(single_layer_s_pattern_proof(mask, cap)).replay_ok

    checked = 0
    for n in range(0, 6):
        for chars in product('-SPc', repeat=n):
            if n and chars[-1] == '-':
                continue
            s = ''.join(chars)
            if not is_craftable_column(s):
                continue
            assert verify_proof(corner_raw_proof(s, max(1, n))).replay_ok
            checked += 1

    clear_proof_caches()

    rng = random.Random(20260717)
    event_nodes = 0
    for _ in range(5):
        s = make_case(rng, rng.randint(7, 80))
        audit = verify_proof(corner_raw_proof(s, len(s)))
        assert audit.replay_ok
        event_nodes = max(event_nodes, audit.unique_nodes)

    clear_proof_caches()
    half_checked = 0
    vals = columns(2)
    for a in vals:
        for b in vals:
            target = half_code(a, b, 2)
            if not is_buildable_half(target, 2):
                continue
            assert verify_proof(half_raw_proof(target, 2)).replay_ok
            half_checked += 1

    # Cap-3 is already exact at the membership level; audit a deterministic
    # cross-section of its raw proof DAGs rather than re-verifying 1,796 large
    # DAG roots independently.
    clear_proof_caches()
    vals3 = columns(3)
    sampled = 0
    for a in vals3[::5]:
        for b in vals3[::7]:
            target = half_code(a, b, 3)
            if not is_buildable_half(target, 3):
                continue
            assert verify_proof(half_raw_proof(target, 3)).replay_ok
            sampled += 1

    print({
        'corner_small': checked,
        'corner_event_high': 5,
        'max_event_nodes': event_nodes,
        'half_cap2': half_checked,
        'half_cap3_sample': sampled,
    })


if __name__ == '__main__':
    main()
