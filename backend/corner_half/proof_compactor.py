from __future__ import annotations

from functools import lru_cache

from .proof_dag import (
    ProofDagError,
    ProofNode,
    cut_proof,
    empty_shape_proof,
    raw_input_proof,
    rotate_proof,
    single_cell_proof,
    single_layer_s_pattern_proof,
    s_only_shape_proof,
    stack_proof,
    swap_proof,
)
from .structural_physics import EMPTY, ORDINARY, code, is_stable, parse


def _normalized(value: str, cap: int) -> str:
    return code(parse(value, cap))


def _single_layer_mask(value: str, cap: int) -> int | None:
    rows = parse(value, cap)
    if len(rows) != 1 or any(cell not in (EMPTY, ORDINARY) for cell in rows[0]):
        return None
    return sum((rows[0][q] == ORDINARY) << q for q in range(4))


def _rotate_if_needed(node: ProofNode, turns: int) -> ProofNode:
    return node if turns % 4 == 0 else rotate_proof(node, turns)


@lru_cache(maxsize=None)
def fast_empty_shape_proof(cap: int) -> ProofNode:
    """Derive the empty shape in two cuts instead of via a fabricated cell."""
    east = cut_proof(raw_input_proof(cap), "east")
    result = cut_proof(east, "west")
    if result.result:
        # Keep the historical proof as a total fallback if operation semantics
        # are ever changed by the core kernel.
        return empty_shape_proof(cap)
    return result


@lru_cache(maxsize=None)
def fast_single_layer_s_pattern_proof(mask: int, cap: int) -> ProofNode:
    """Small exact constructor for all sixteen one-layer ordinary masks."""
    if not 0 <= mask < 16:
        raise ProofDagError("mask must be 0..15")
    expected = code([[ORDINARY if mask & (1 << q) else EMPTY for q in range(4)]])
    if mask == 0:
        candidate = fast_empty_shape_proof(cap)
        return candidate if candidate.result == expected else single_layer_s_pattern_proof(mask, cap)
    if mask == 0b1111:
        return raw_input_proof(cap)
    if mask & (mask - 1) == 0:
        q = mask.bit_length() - 1
        candidate = single_cell_proof(q, cap)
        return candidate if candidate.result == expected else single_layer_s_pattern_proof(mask, cap)

    # Any adjacent pair is a rotation of one cutter output.
    pair = cut_proof(raw_input_proof(cap), "east")
    for turns in range(4):
        candidate = _rotate_if_needed(pair, turns)
        if candidate.result == expected:
            return candidate

    # A three-cell row is one single-cell east half plus the opposite full half.
    raw = raw_input_proof(cap)
    for q in range(4):
        one = single_cell_proof(q, cap)
        for output in (0, 1):
            joined = swap_proof(one, raw, output)
            for turns in range(4):
                candidate = _rotate_if_needed(joined, turns)
                if candidate.result == expected:
                    return candidate

    # Diagonal pairs (and any future exceptional mask) are exactly the union of
    # disjoint single-cell pieces under Stack.
    columns = [q for q in range(4) if mask & (1 << q)]
    if columns:
        current = single_cell_proof(columns[0], cap)
        for q in columns[1:]:
            current = stack_proof(current, single_cell_proof(q, cap))
        if current.result == expected:
            return current

    return single_layer_s_pattern_proof(mask, cap)


@lru_cache(maxsize=None)
def fast_s_only_shape_proof(target: str, cap: int) -> ProofNode:
    normalized = _normalized(target, cap)
    rows = parse(normalized, cap)
    if any(cell not in (EMPTY, ORDINARY) for row in rows for cell in row):
        raise ProofDagError("target is not S-only")
    if normalized and not is_stable(rows):
        raise ProofDagError("S-only target is unstable")
    if not normalized:
        return fast_empty_shape_proof(cap)
    layer_codes = normalized.split(":")
    top_row = rows[len(layer_codes) - 1]
    mask = sum((top_row[q] == ORDINARY) << q for q in range(4))
    top = fast_single_layer_s_pattern_proof(mask, cap)
    if len(layer_codes) == 1:
        if top.result == normalized:
            return top
        return s_only_shape_proof(normalized, cap)
    prefix = fast_s_only_shape_proof(":".join(layer_codes[:-1]), cap)
    result = stack_proof(prefix, top)
    if result.result != normalized:
        return s_only_shape_proof(normalized, cap)
    return result


def _is_s_only(value: str, cap: int) -> bool:
    rows = parse(value, cap)
    return all(cell in (EMPTY, ORDINARY) for row in rows for cell in row) and (not value or is_stable(rows))


def compact_proof(root: ProofNode) -> ProofNode:
    """Replace expensive S-only helper subproofs with exact smaller proofs.

    Result codes are preserved exactly. The caller must run the independent raw
    proof verifier after compaction; any future physics change therefore fails
    closed rather than accepting a stale optimization.
    """
    memo: dict[int, ProofNode] = {}

    def visit(node: ProofNode) -> ProofNode:
        ident = id(node)
        cached = memo.get(ident)
        if cached is not None:
            return cached
        if node.operation == "RAW_INPUT":
            result = node
        elif _is_s_only(node.result, node.cap):
            result = fast_s_only_shape_proof(node.result, node.cap)
        else:
            children = tuple(visit(child) for child in node.children)
            result = ProofNode(
                operation=node.operation,
                cap=node.cap,
                result=node.result,
                children=children,
                parameter=node.parameter,
                note=node.note,
            )
        memo[ident] = result
        return result

    return visit(root)


def clear_compactor_caches() -> None:
    fast_empty_shape_proof.cache_clear()
    fast_single_layer_s_pattern_proof.cache_clear()
    fast_s_only_shape_proof.cache_clear()
