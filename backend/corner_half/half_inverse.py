"""Exact all-layer Cut/Swap inverse relations built on the Half theorem.

The module exposes two relations needed by the TMAM integration branch:

* ``canonical_cut_inverse(H)`` returns a buildable full parent whose east
  Cutter output is exactly the buildable half ``H``.
* ``swap_inverse_candidates(X)`` returns every cut-axis orientation in which
  the geometric east and west halves of ``X`` are both in the exact Half
  family, together with raw-input proof DAGs for the two Swapper operands.

No arbitrary missing half is guessed.  Every parent is synthesized from
Corner/Half certificates and independently replayed with the structural game
operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from .half_family import analyze_half
from .proof_dag import (
    ProofNode,
    cut_proof,
    half_raw_proof,
    rotate_proof,
    s_only_shape_proof,
    swap_proof,
    verify_proof,
)
from .structural_ops import cut, rotate, swap
from .structural_physics import EMPTY, ORDINARY, code, is_stable, parse


class HalfInverseError(ValueError):
    pass


@dataclass(frozen=True)
class CutHalfInverse:
    target_half: str
    cap: int
    parent_full: str
    discarded_west: str
    parent_proof: ProofNode
    cut_result_proof: ProofNode
    replay_ok: bool


@dataclass(frozen=True)
class SwapFullInverse:
    target: str
    cap: int
    rotation_cw: int
    oriented_target: str
    east_half: str
    west_half: str
    west_as_east: str
    east_operand: str
    west_operand: str
    swap_output: str
    final_result: str
    east_operand_proof: ProofNode
    west_operand_proof: ProofNode
    result_proof: ProofNode
    replay_ok: bool


def _normalize_full(code_value: str, cap: int) -> tuple[list[list[str]], str]:
    rows = parse(code_value, cap)
    return rows, code(rows)


def _geometric_halves(rows: list[list[str]], cap: int) -> tuple[list[list[str]], list[list[str]]]:
    east = [[row[0], row[1], EMPTY, EMPTY] for row in rows[:cap]]
    west = [[EMPTY, EMPTY, row[2], row[3]] for row in rows[:cap]]
    return east, west


def _east_tower_half(height: int, cap: int) -> str:
    rows = [
        [ORDINARY, ORDINARY, EMPTY, EMPTY] if layer < height else [EMPTY] * 4
        for layer in range(cap)
    ]
    return code(rows)


@lru_cache(maxsize=200_000)
def canonical_cut_inverse(code_value: str, layers: int | None = None) -> CutHalfInverse:
    """Return a non-circular, buildable Cutter parent for one east half.

    The parent is ``(H | T,T)`` where ``T`` is a solid normal tower.  The west
    towers cannot shatter target crystals across the cut boundary.  Cutting the
    parent therefore returns ``H`` exactly.
    """

    analysis = analyze_half(code_value, layers)
    if not analysis.buildable:
        raise HalfInverseError("target is not in the exact Half family")
    cap = analysis.cap
    height = max(1, len(analysis.left_column), len(analysis.right_column))

    half_proof = half_raw_proof(analysis.normalized_code, cap)
    tower_east_code = _east_tower_half(height, cap)
    tower_east = s_only_shape_proof(tower_east_code, cap)
    tower_west = rotate_proof(tower_east, 2)
    parent = swap_proof(half_proof, tower_west, 0)
    result = cut_proof(parent, "east")

    parent_rows = parse(parent.result, cap)
    east, west = cut(parent_rows, cap)
    ok = (
        result.result == analysis.normalized_code
        and code(east) == analysis.normalized_code
        and parent.result == code(parent_rows)
        and is_stable(parent_rows)
        and verify_proof(result).replay_ok
    )
    return CutHalfInverse(
        target_half=analysis.normalized_code,
        cap=cap,
        parent_full=parent.result,
        discarded_west=code(west),
        parent_proof=parent,
        cut_result_proof=result,
        replay_ok=ok,
    )


def _candidate_for_orientation(
    target_rows: list[list[str]], target_code: str, cap: int, rotation_cw: int
) -> SwapFullInverse | None:
    oriented = rotate(target_rows, rotation_cw)
    east, west = _geometric_halves(oriented, cap)
    east_code = code(east)
    west_code = code(west)
    west_as_east_rows = rotate(west, 2)
    west_as_east = code(west_as_east_rows)

    east_analysis = analyze_half(east_code, cap)
    west_analysis = analyze_half(west_as_east, cap)
    if not (east_analysis.buildable and west_analysis.buildable):
        return None

    east_proof = half_raw_proof(east_analysis.normalized_code, cap)
    west_east_proof = half_raw_proof(west_analysis.normalized_code, cap)
    west_proof = rotate_proof(west_east_proof, 2)
    joined = swap_proof(east_proof, west_proof, 0)
    final = rotate_proof(joined, (-rotation_cw) % 4)

    direct_outputs = swap(
        parse(east_proof.result, cap), parse(west_proof.result, cap), cap
    )
    direct_final = rotate(direct_outputs[0], (-rotation_cw) % 4)
    ok = (
        code(direct_outputs[0]) == code(oriented)
        and code(direct_final) == target_code
        and final.result == target_code
        and verify_proof(final).replay_ok
    )
    return SwapFullInverse(
        target=target_code,
        cap=cap,
        rotation_cw=rotation_cw,
        oriented_target=code(oriented),
        east_half=east_code,
        west_half=west_code,
        west_as_east=west_as_east,
        east_operand=east_proof.result,
        west_operand=west_proof.result,
        swap_output=joined.result,
        final_result=final.result,
        east_operand_proof=east_proof,
        west_operand_proof=west_proof,
        result_proof=final,
        replay_ok=ok,
    )


def swap_inverse_candidates(
    target: str, layers: int, *, deduplicate: bool = True
) -> tuple[SwapFullInverse, ...]:
    """Return every exact Swapper decomposition modulo 180-degree duplication.

    Only the two distinct cutter axes are needed.  A target is Swappable iff at
    least one orientation has both geometric halves in the exact Half family.
    """

    rows, normalized = _normalize_full(target, layers)
    results: list[SwapFullInverse] = []
    seen: set[tuple[str, str, str]] = set()
    for rotation_cw in (0, 1):
        candidate = _candidate_for_orientation(rows, normalized, layers, rotation_cw)
        if candidate is None:
            continue
        key = (candidate.east_operand, candidate.west_operand, candidate.final_result)
        if deduplicate and key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    return tuple(results)


def first_swap_inverse(target: str, layers: int) -> SwapFullInverse:
    candidate = next(iter(swap_inverse_candidates(target, layers)), None)
    if candidate is None:
        raise HalfInverseError("target has no Swapper decomposition through the exact Half family")
    return candidate


def is_swappable_full(target: str, layers: int) -> bool:
    rows, normalized = _normalize_full(target, layers)
    for rotation_cw in (0, 1):
        oriented = rotate(rows, rotation_cw)
        east, west = _geometric_halves(oriented, layers)
        west_as_east = rotate(west, 2)
        if analyze_half(code(east), layers).buildable and analyze_half(
            code(west_as_east), layers
        ).buildable:
            return True
    return False


__all__ = [
    "CutHalfInverse",
    "HalfInverseError",
    "SwapFullInverse",
    "canonical_cut_inverse",
    "first_swap_inverse",
    "is_swappable_full",
    "swap_inverse_candidates",
]
