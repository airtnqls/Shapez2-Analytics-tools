"""Fast exact audit of the all-layer Cut/Swap inverse API.

The expensive raw proofs share large subtrees.  This test therefore builds all
roots first and verifies each proof forest once, rather than recursively
replaying the same child for every target.
"""
from __future__ import annotations

from itertools import product
import random

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_family import is_buildable_half
from corner_half.half_inverse import canonical_cut_inverse
from corner_half.proof_dag import clear_proof_caches, verify_proof_forest

from test_inverse_full_cap2 import main as exhaustive_cap2_main


def _columns(cap: int) -> list[str]:
    out = {""}
    for n in range(1, cap + 1):
        for chars in product("-SPc", repeat=n):
            if chars[-1] == "-":
                continue
            value = "".join(chars)
            if is_craftable_column(value):
                out.add(value)
    return sorted(out)


def _half_code(left: str, right: str, cap: int) -> str:
    return ":".join(
        (left[layer] if layer < len(left) else "-")
        + (right[layer] if layer < len(right) else "-")
        + "--"
        for layer in range(cap)
    )


def main() -> None:
    exhaustive_cap2_main()

    # High-cap witnesses exercise the all-layer formulas without enumerating a
    # cap-dependent concrete HalfSet.  All roots are verified as one DAG.
    rng = random.Random(20260717)
    small_columns = _columns(4)
    clear_proof_caches()
    roots = []
    attempted = accepted = 0
    for _ in range(500):
        cap = rng.randint(4, 80)
        left = rng.choice(small_columns)
        right = rng.choice(small_columns)
        target = _half_code(left, right, cap)
        attempted += 1
        if not is_buildable_half(target, cap):
            continue
        witness = canonical_cut_inverse(target, cap)
        assert witness.replay_ok
        roots.append(witness.cut_result_proof)
        accepted += 1
    audit = verify_proof_forest(roots)
    assert audit.replay_ok and audit.all_stable
    print(
        {
            "high_cut_attempted": attempted,
            "high_cut_accepted": accepted,
            "high_cut_unique_nodes": audit.unique_nodes,
            "high_cut_max_depth": audit.max_depth,
        }
    )


if __name__ == "__main__":
    main()
