from __future__ import annotations

from corner_half import (
    construct_corner,
    construct_half,
    corner_raw_proof,
    half_raw_proof,
    is_buildable_half,
    is_craftable_column,
    verify_proof,
)


def main() -> None:
    for column in ('S-S-S-S-c', 'PcS-S-c', '-S-c'):
        assert is_craftable_column(column)
        assert construct_corner(column, max(1, len(column))).replay_ok
        assert verify_proof(corner_raw_proof(column, max(1, len(column)))).replay_ok

    half = 'SS--:cS--'
    assert is_buildable_half(half, 2)
    assert construct_half(half, 2).replay_ok
    assert verify_proof(half_raw_proof(half, 2)).replay_ok
    print({'corner_examples': 3, 'half_examples': 1, 'status': 'PASS'})


if __name__ == '__main__':
    main()
