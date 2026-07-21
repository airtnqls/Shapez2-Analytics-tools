"""Replay-certified positive proof accelerator for exact global predecessors.

The complete Corner theorem remains the fallback.  This module is used only
when the all-layer legacy-style global predecessor already produces the exact
requested Corner column in one Pin Push and every helper column is on the
non-event route.  It then builds the predecessor from two stable natural
halves, applies the Pin Pusher once, and restores the canonical support towers
once instead of after every Corner-IR step.
"""
from __future__ import annotations

from .global_predecessor import GlobalPredecessorError, GlobalRelation, compile_global_predecessor
from .structural_physics import EMPTY, ORDINARY, code, column, is_stable, parse


def _tower(height: int) -> str:
    return ORDINARY * max(0, height)


def try_global_corner_raw_proof(column_value: str, cap: int):
    """Return a smaller exact ``ProofNode`` or ``None`` for safe fallback.

    Importing :mod:`proof_dag` inside the function avoids a module import cycle.
    Every returned node is independently checked by ``verify_proof`` later.
    """
    from . import proof_dag as dag

    normalized = column_value.rstrip(EMPTY)
    if not normalized or len(normalized) != cap:
        return None
    try:
        cert = compile_global_predecessor(normalized, cap)
    except (GlobalPredecessorError, ValueError):
        return None
    if not cert.replay_ok or cert.relation is not GlobalRelation.EXACT:
        return None
    if not cert.predecessor_is_natural:
        return None

    a, b, c, d = cert.predecessor_columns
    predecessor_rows = parse(cert.predecessor, cap)
    # The two-half assembly is the same acyclic lower stratum used by C7.
    bc_rows = [[b[l] if l < len(b) else EMPTY, c[l] if l < len(c) else EMPTY, EMPTY, EMPTY] for l in range(cap)]
    da_rows = [[d[l] if l < len(d) else EMPTY, a[l] if l < len(a) else EMPTY, EMPTY, EMPTY] for l in range(cap)]
    if not (is_stable(bc_rows) and is_stable(da_rows)):
        return None

    try:
        bc = dag.half_from_corner_proofs(b, c, cap, True)
        da_east = dag.half_from_corner_proofs(d, a, cap, True)
        da_west = dag.rotate_proof(da_east, 2)
        joined = dag.swap_proof(bc, da_west, 0)  # (B,C,D,A)
        predecessor = dag.rotate_proof(joined, 1)  # (A,B,C,D)
        if predecessor.result != cert.predecessor:
            return None
        pushed = dag.pin_push_proof(predecessor)
        if pushed.result != cert.pushed or column(parse(pushed.result, cap), 0) != normalized:
            return None

        # Replace B,C,D with one shared solid-tower helper.  The exact cut/swap
        # kernel is replayed here, so any crystal boundary interaction simply
        # rejects this accelerator and falls back to the complete constructor.
        full_tower = dag.full_s_tower_proof(cap, cap)
        west_towers = dag.cut_proof(full_tower, "west")
        first = dag.swap_proof(pushed, west_towers, 0)  # (A,B,T,T)
        rotated = dag.rotate_proof(first, 1)            # (T,A,B,T)
        second = dag.swap_proof(rotated, west_towers, 0)  # (T,A,T,T)
        final = dag.rotate_proof(second, 3)             # (A,T,T,T)
    except (dag.ProofDagError, ValueError):
        return None

    expected_rows = [
        [
            normalized[layer] if layer < len(normalized) else EMPTY,
            ORDINARY,
            ORDINARY,
            ORDINARY,
        ]
        for layer in range(cap)
    ]
    expected = code(expected_rows)
    if final.result != expected or not is_stable(parse(final.result, cap)):
        return None
    return final


__all__ = ["try_global_corner_raw_proof"]
