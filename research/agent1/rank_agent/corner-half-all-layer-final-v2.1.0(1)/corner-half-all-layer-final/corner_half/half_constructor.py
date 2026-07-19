"""Constructive proof for the all-layer Half theorem.

For a stable half ``H=(u,v)``, with both columns in the exact Corner language:

1. construct ``v`` beside a solid S tower in the east half;
2. construct ``u`` beside a solid S tower in the west half (opposite support
   orientation, allowed by the Corner Exchange Lemma);
3. swap the two prefabricated halves, obtaining ``(v,T,T,u)``;
4. rotate clockwise, obtaining ``(u,v,T,T)``;
5. cut and keep the east half.  No boundary crystal pair exists because the
   discarded half is the normal tower pair, and the kept half is unchanged by
   gravity because it was assumed stable.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .corner_constructor import CornerConstructionCertificate, construct_corner
from .half_family import HalfAnalysis, analyze_half
from .structural_ops import cut, rotate, swap
from .structural_physics import EMPTY, ORDINARY, code, column, is_stable


class HalfConstructionError(ValueError):
    pass


@dataclass(frozen=True)
class HalfConstructionCertificate:
    target: str
    cap: int
    analysis: HalfAnalysis
    left_corner: CornerConstructionCertificate
    right_corner: CornerConstructionCertificate
    right_east_prefab: str
    left_west_prefab: str
    after_swap: str
    after_rotation: str
    cut_east: str
    discarded_west: str
    replay_ok: bool


def _rows(columns: tuple[str, str, str, str], cap: int) -> list[list[str]]:
    return [
        [columns[q][l] if l < len(columns[q]) else EMPTY for q in range(4)]
        for l in range(cap)
    ]


def _half_code(rows: list[list[str]], q0: int, q1: int) -> str:
    parts=[]
    for row in rows:
        parts.append(row[q0]+row[q1]+EMPTY+EMPTY)
    return code([list(x) for x in parts])


@lru_cache(maxsize=2_048)
def construct_half(code_value: str, layers: int) -> HalfConstructionCertificate:
    analysis=analyze_half(code_value,layers)
    if not analysis.buildable:
        if analysis.left_rejection is not None:
            why=f"left column rejected by {analysis.left_rejection.rule}"
        elif analysis.right_rejection is not None:
            why=f"right column rejected by {analysis.right_rejection.rule}"
        else:
            why="joint half is unstable"
        raise HalfConstructionError(why)

    left=analysis.left_column
    right=analysis.right_column
    left_cert=construct_corner(left,layers)
    right_cert=construct_corner(right,layers)
    if not (left_cert.replay_ok and right_cert.replay_ok):
        raise HalfConstructionError("a Corner parent certificate did not replay")

    tower=ORDINARY*layers
    # First prefab keeps the east half (right,T).  Second keeps the west half
    # (T,left); the latter is the reflected support orientation of the same
    # Corner construction calculus.
    prefab_r=_rows((right,tower,"",""),layers)
    prefab_l=_rows(("","",tower,left),layers)
    if not is_stable(prefab_r):
        raise HalfConstructionError("right+solid east prefab is unstable")
    if not is_stable(prefab_l):
        raise HalfConstructionError("solid+left west prefab is unstable")

    combined,_=swap(prefab_r,prefab_l,layers)
    rotated=rotate(combined,1)
    east,west=cut(rotated,layers)
    east_cols=(column(east,0),column(east,1))
    ok=(
        east_cols==(left,right)
        and code(east)==analysis.normalized_code
        and is_stable(east)
    )
    return HalfConstructionCertificate(
        target=analysis.normalized_code,
        cap=layers,
        analysis=analysis,
        left_corner=left_cert,
        right_corner=right_cert,
        right_east_prefab=code(prefab_r),
        left_west_prefab=code(prefab_l),
        after_swap=code(combined),
        after_rotation=code(rotated),
        cut_east=code(east),
        discarded_west=code(west),
        replay_ok=ok,
    )


__all__=["HalfConstructionCertificate","HalfConstructionError","construct_half"]
