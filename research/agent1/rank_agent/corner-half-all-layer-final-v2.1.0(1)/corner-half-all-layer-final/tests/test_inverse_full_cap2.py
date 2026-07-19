"""Efficient exhaustive audit of the canonical Cut/Swap inverse relations.

This avoids re-verifying the same shared raw proof subtree thousands of times:
all roots are built first and then checked by ``verify_proof_forest`` once.
"""
from __future__ import annotations

from itertools import product
from time import perf_counter

from corner_half.corner_dfa import is_craftable_column
from corner_half.half_family import analyze_half, is_buildable_half
from corner_half.half_inverse import (
    canonical_cut_inverse,
    is_swappable_full,
    swap_inverse_candidates,
)
from corner_half.proof_dag import clear_proof_caches, verify_proof_forest
from corner_half.structural_ops import rotate, swap
from corner_half.structural_physics import code, parse


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


def _direct_swap_axes(target: str, cap: int) -> tuple[int, ...]:
    """Canonical forward replay without constructing raw proof DAGs."""
    target_rows = parse(target, cap)
    normalized = code(target_rows)
    accepted: list[int] = []
    for rotation_cw in (0, 1):
        oriented = rotate(target_rows, rotation_cw)
        east = [[row[0], row[1], "-", "-"] for row in oriented]
        west = [["-", "-", row[2], row[3]] for row in oriented]
        west_as_east = rotate(west, 2)
        east_analysis = analyze_half(code(east), cap)
        west_analysis = analyze_half(code(west_as_east), cap)
        if not (east_analysis.buildable and west_analysis.buildable):
            continue
        west_operand = rotate(parse(west_analysis.normalized_code, cap), 2)
        joined, _ = swap(parse(east_analysis.normalized_code, cap), west_operand, cap)
        final = rotate(joined, (-rotation_cw) % 4)
        assert code(final) == normalized
        accepted.append(rotation_cw)
    return tuple(accepted)


def main() -> None:
    # Every cap-3 Half obtains a real raw-input Cutter parent.
    values = _columns(3)
    half_targets = [
        _half_code(left, right, 3)
        for left in values
        for right in values
        if is_buildable_half(_half_code(left, right, 3), 3)
    ]
    assert len(half_targets) == 1_796
    clear_proof_caches()
    cut_roots = []
    for target in half_targets:
        candidate = canonical_cut_inverse(target, 3)
        assert candidate.replay_ok
        cut_roots.append(candidate.cut_result_proof)
    cut_audit = verify_proof_forest(cut_roots)
    assert cut_audit.replay_ok and cut_audit.all_stable

    # All 65,536 cap-2 full structural targets are checked.  For every
    # accepted axis, canonical operands are forward-replayed to the target.
    row_values = tuple("".join(row) for row in product("-SPc", repeat=4))
    swap_targets: list[str] = []
    candidate_axes = 0
    for bottom in row_values:
        for top in row_values:
            target = code([list(bottom), list(top)])
            axes = _direct_swap_axes(target, 2)
            assert bool(axes) == is_swappable_full(target, 2)
            if axes:
                swap_targets.append(target)
                candidate_axes += len(axes)
    assert len(swap_targets) == 35_017
    assert candidate_axes == 65_522

    # Audit a deterministic 2,000-target cross-section as raw operation DAGs,
    # sharing common subproofs across the whole forest.
    sample = swap_targets[:: max(1, len(swap_targets) // 2_000)][:2_000]
    clear_proof_caches()
    swap_roots = []
    for target in sample:
        candidates = swap_inverse_candidates(target, 2)
        assert candidates and all(candidate.replay_ok for candidate in candidates)
        swap_roots.extend(candidate.result_proof for candidate in candidates)
    swap_audit = verify_proof_forest(swap_roots)
    assert swap_audit.replay_ok and swap_audit.all_stable

    print(
        {
            "cut_cap3": len(half_targets),
            "cut_unique_nodes": cut_audit.unique_nodes,
            "full_cap2": len(row_values) ** 2,
            "swappable_cap2": len(swap_targets),
            "candidate_axes": candidate_axes,
            "raw_swap_sample": len(sample),
            "raw_swap_roots": len(swap_roots),
            "swap_unique_nodes": swap_audit.unique_nodes,
        }
    )


if __name__ == "__main__":
    main()
