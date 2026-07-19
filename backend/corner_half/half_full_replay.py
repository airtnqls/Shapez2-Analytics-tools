"""Raw-operation proof replay for the exact all-layer Half theorem."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .corner_full_replay import CornerFullReplay, replay_corner_full
from .half_family import analyze_half
from .structural_ops import cut, rotate, swap
from .structural_physics import code, column, is_stable, parse


class HalfFullReplayError(ValueError):
    pass


@dataclass(frozen=True)
class HalfFullReplay:
    target: str
    cap: int
    left_corner: CornerFullReplay
    right_corner: CornerFullReplay
    fixture_v_tower: str
    fixture_tower_u: str
    rotated_fixture_tower_u: str
    after_swap: str
    after_rotate: str
    east_result: str
    west_discarded: str
    all_intermediate_stable: bool
    replay_ok: bool


@lru_cache(maxsize=200_000)
def replay_half_full(code_value: str, layers: int | None = None) -> HalfFullReplay:
    analysis=analyze_half(code_value,layers)
    if not analysis.buildable:
        raise HalfFullReplayError("half is outside the exact stable-Corner-pair family")
    cap=analysis.cap
    u,v=analysis.left_column,analysis.right_column
    left=replay_corner_full(u,cap)
    right=replay_corner_full(v,cap)
    if not (left.replay_ok and right.replay_ok):
        raise HalfFullReplayError("child Corner raw replay failed")

    left_full=parse(left.final_full_shape,cap)   # [u,T,T,T]
    right_full=parse(right.final_full_shape,cap) # [v,T,T,T]
    fixture_v,_=cut(right_full,cap)              # [v,T]
    left_rot=rotate(left_full,1)                  # [T,u,T,T]
    fixture_u,_=cut(left_rot,cap)                 # [T,u]
    fixture_u_west=rotate(fixture_u,2)            # west [T,u]
    joined,_=swap(fixture_v,fixture_u_west,cap)   # [v,T,T,u]
    oriented=rotate(joined,1)                     # [u,v,T,T]
    east,west=cut(oriented,cap)                   # stable target pair

    states=(fixture_v,fixture_u,fixture_u_west,joined,oriented,east,west)
    stable=all(is_stable(x) for x in states)
    ok=stable and code(east)==analysis.normalized_code
    return HalfFullReplay(
        target=analysis.normalized_code,
        cap=cap,
        left_corner=left,
        right_corner=right,
        fixture_v_tower=code(fixture_v),
        fixture_tower_u=code(fixture_u),
        rotated_fixture_tower_u=code(fixture_u_west),
        after_swap=code(joined),
        after_rotate=code(oriented),
        east_result=code(east),
        west_discarded=code(west),
        all_intermediate_stable=stable,
        replay_ok=ok,
    )


__all__=["HalfFullReplay","HalfFullReplayError","replay_half_full"]
