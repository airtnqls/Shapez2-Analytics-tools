"""Recursively replayable raw-operation proof DAGs for Corner and Half.

Unlike the compact certificates, every non-leaf node here is one actual
structural game operation.  The only leaf is the raw one-layer ``SSSS`` input.
Repeated subproofs are shared by memoization, so the object graph is a DAG.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from .corner_full_replay import replay_corner_full
from .corner_regions import Route, analyze_column
from .structural_ops import cut, generate, input_full, rotate, stack, swap
from .structural_physics import EMPTY, ORDINARY, PIN, code, column, is_stable, parse, push_pin


class ProofDagError(ValueError):
    pass


@dataclass(frozen=True)
class ProofNode:
    operation: str
    cap: int
    result: str
    children: tuple["ProofNode", ...] = ()
    parameter: int | str | None = None
    note: str = ""


@dataclass(frozen=True)
class ProofAudit:
    result: str
    unique_nodes: int
    operation_nodes: int
    raw_leaves: int
    max_depth: int
    all_stable: bool
    replay_ok: bool


@dataclass(frozen=True)
class ProofForestAudit:
    results: tuple[str, ...]
    unique_nodes: int
    operation_nodes: int
    raw_leaves: int
    edges: int
    max_depth: int
    all_stable: bool
    replay_ok: bool


@lru_cache(maxsize=16_384)
def _rows(value: str, cap: int):
    # All structural operations copy their operands before mutation, so sharing
    # parsed immutable-by-contract rows is safe and removes repeated O(L)
    # decoding throughout a large proof DAG.
    return parse(value, cap)


def _node(operation: str, cap: int, result_rows, children=(), parameter=None, note="") -> ProofNode:
    result = code(result_rows)
    return ProofNode(operation, cap, result, tuple(children), parameter, note)


@lru_cache(maxsize=None)
def raw_input_proof(cap: int) -> ProofNode:
    if cap < 1:
        raise ProofDagError("cap must be positive")
    return _node("RAW_INPUT", cap, input_full(), note="one-layer SSSS")


def rotate_proof(child: ProofNode, steps_cw: int) -> ProofNode:
    return _node("ROTATE", child.cap, rotate(_rows(child.result, child.cap), steps_cw), (child,), steps_cw % 4)


def cut_proof(child: ProofNode, side: str) -> ProofNode:
    east, west = cut(_rows(child.result, child.cap), child.cap)
    if side == "east":
        out = east
    elif side == "west":
        out = west
    else:
        raise ProofDagError(f"bad cut side {side!r}")
    return _node("CUT", child.cap, out, (child,), side)


def swap_proof(first: ProofNode, second: ProofNode, output: int = 0) -> ProofNode:
    if first.cap != second.cap or output not in (0, 1):
        raise ProofDagError("bad swap proof")
    outs = swap(_rows(first.result, first.cap), _rows(second.result, second.cap), first.cap)
    return _node("SWAP", first.cap, outs[output], (first, second), output)


def stack_proof(bottom: ProofNode, top: ProofNode) -> ProofNode:
    if bottom.cap != top.cap:
        raise ProofDagError("stack cap mismatch")
    out = stack(_rows(bottom.result, bottom.cap), _rows(top.result, top.cap), bottom.cap)
    return _node("STACK", bottom.cap, out, (bottom, top))


def generate_proof(child: ProofNode) -> ProofNode:
    return _node("GENERATE", child.cap, generate(_rows(child.result, child.cap), child.cap), (child,))


def pin_push_proof(child: ProofNode) -> ProofNode:
    return _node("PIN_PUSH", child.cap, push_pin(_rows(child.result, child.cap), child.cap), (child,))


@lru_cache(maxsize=None)
def single_cell_proof(column_index: int, cap: int) -> ProofNode:
    if not 0 <= column_index < 4:
        raise ProofDagError("column must be 0..3")
    raw = raw_input_proof(cap)
    east = cut_proof(raw, "east")
    straddled = rotate_proof(east, 1)
    one = cut_proof(straddled, "east")
    rows = _rows(one.result, cap)
    positions = [q for q in range(4) if rows and rows[0][q] != EMPTY]
    if len(positions) != 1:
        raise ProofDagError(f"single-cell derivation failed: {one.result}")
    return rotate_proof(one, (column_index - positions[0]) % 4)


@lru_cache(maxsize=None)
def empty_shape_proof(cap: int) -> ProofNode:
    # q0 is in the east half, so its west cutter output is empty.
    return cut_proof(single_cell_proof(0, cap), "west")


@lru_cache(maxsize=None)
def single_layer_s_pattern_proof(mask: int, cap: int) -> ProofNode:
    if not 0 <= mask < 16:
        raise ProofDagError("mask must be 0..15")
    current = empty_shape_proof(cap)
    for q in range(4):
        if mask & (1 << q):
            current = stack_proof(current, single_cell_proof(q, cap))
    expected = code([[ORDINARY if mask & (1 << q) else EMPTY for q in range(4)]])
    if current.result != expected:
        raise ProofDagError(("single layer S pattern", mask, current.result, expected))
    return current


@lru_cache(maxsize=None)
def s_only_shape_proof(target: str, cap: int) -> ProofNode:
    normalized = code(_rows(target, cap))
    rows = _rows(normalized, cap)
    if any(cell not in (EMPTY, ORDINARY) for row in rows for cell in row):
        raise ProofDagError("target is not S-only")
    if normalized and not is_stable(rows):
        raise ProofDagError("S-only target is unstable")
    if not normalized:
        return empty_shape_proof(cap)
    layer_codes = normalized.split(":")
    prefix = ":".join(layer_codes[:-1])
    current = s_only_shape_proof(prefix, cap)
    top_row = rows[len(layer_codes) - 1]
    mask = sum((top_row[q] == ORDINARY) << q for q in range(4))
    current = stack_proof(current, single_layer_s_pattern_proof(mask, cap))
    if current.result != normalized:
        raise ProofDagError(("S-only layer-stack failed", normalized, current.result))
    return current


@lru_cache(maxsize=None)
def one_pin_proof(cap: int, target_column: int = 0) -> ProofNode:
    if cap < 1 or not 0 <= target_column < 4:
        raise ProofDagError("bad one-pin dimensions")
    source = single_cell_proof(0, cap)
    pin_pair = pin_push_proof(source)
    if cap == 1:
        result = rotate_proof(pin_pair, target_column)
        if column(_rows(result.result, cap), target_column) != PIN:
            raise ProofDagError("cap1 one-pin proof failed")
        return result

    pedestal = s_only_shape_proof(
        ":".join("-SSS" for _ in range(cap - 1)), cap
    )
    generated = generate_proof(pedestal)
    capped = stack_proof(generated, pin_pair)

    trigger_seed = single_layer_s_pattern_proof(0b0111, cap)
    trigger_generated = generate_proof(trigger_seed)
    trigger_west = cut_proof(trigger_generated, "west")
    trigger_shape = swap_proof(capped, trigger_west, 0)
    east = cut_proof(trigger_shape, "east")
    split = rotate_proof(east, 1)
    isolated = cut_proof(split, "east")
    q0_pin = rotate_proof(isolated, 3)
    result = rotate_proof(q0_pin, target_column)
    rows = _rows(result.result, cap)
    occupied_count = sum(cell != EMPTY for row in rows for cell in row)
    if column(rows, target_column) != PIN or occupied_count != 1:
        raise ProofDagError(("one-pin proof failed", cap, target_column, result.result))
    return result


@lru_cache(maxsize=None)
def single_layer_sp_proof(cells: str, cap: int) -> ProofNode:
    if len(cells) != 4 or any(ch not in (EMPTY, ORDINARY, PIN) for ch in cells):
        raise ProofDagError("single_layer_sp_proof expects four -/S/P cells")
    current = empty_shape_proof(cap)
    for q, cell in enumerate(cells):
        if cell == ORDINARY:
            piece = single_cell_proof(q, cap)
        elif cell == PIN:
            piece = one_pin_proof(cap, q)
        else:
            continue
        current = stack_proof(current, piece)
    expected = code([list(cells)])
    if current.result != expected:
        raise ProofDagError(("single-layer S/P proof", cells, current.result, expected))
    return current


@lru_cache(maxsize=None)
def sp_only_shape_proof(target: str, cap: int) -> ProofNode:
    normalized = code(_rows(target, cap))
    rows = _rows(normalized, cap)
    if any(cell not in (EMPTY, ORDINARY, PIN) for row in rows for cell in row):
        raise ProofDagError("target is not S/P-only")
    if normalized and not is_stable(rows):
        raise ProofDagError("S/P-only target is unstable")
    if not normalized:
        return empty_shape_proof(cap)
    layer_codes = normalized.split(":")
    prefix = ":".join(layer_codes[:-1])
    current = sp_only_shape_proof(prefix, cap)
    top_row = "".join(rows[len(layer_codes) - 1])
    current = stack_proof(current, single_layer_sp_proof(top_row, cap))
    if current.result != normalized:
        raise ProofDagError(("S/P layer-stack failed", normalized, current.result))
    return current


@lru_cache(maxsize=None)
def generated_solid_shape_proof(target: str, cap: int) -> ProofNode:
    rows = _rows(target, cap)
    height = 0
    for l, row in enumerate(rows):
        if any(cell != EMPTY for cell in row):
            height = l + 1
    if height == 0:
        return empty_shape_proof(cap)
    # One Generator can create target iff every cell below global height is S/c
    # and all c positions can be represented as gaps before generation.
    for l in range(height):
        if any(cell not in (ORDINARY, "c") for cell in rows[l]):
            raise ProofDagError("not a one-generation solid target")
    seed_rows = [
        [ORDINARY if rows[l][q] == ORDINARY else EMPTY for q in range(4)]
        for l in range(height)
    ]
    seed = s_only_shape_proof(code(seed_rows), cap)
    out = generate_proof(seed)
    if out.result != code(rows):
        raise ProofDagError(("generated solid proof", target, out.result))
    return out


_BUILDING_CORNER: set[tuple[str, int]] = set()
_BUILDING_SHAPE: set[tuple[str, int, bool]] = set()


def _occupied_columns(target: str, cap: int) -> set[int]:
    rows = _rows(target, cap)
    return {q for q in range(4) if any(row[q] != EMPTY for row in rows)}


def _rotate_to_east(target: str, cap: int) -> tuple[str, int] | None:
    rows = _rows(target, cap)
    for k in range(4):
        rotated = rotate(rows, k)
        occ = {q for q in range(4) if any(row[q] != EMPTY for row in rotated)}
        if occ <= {0, 1}:
            return code(rotated), k
    return None


@lru_cache(maxsize=None)
def canonical_column_proof(value: str, cap: int, natural_only: bool = False) -> ProofNode:
    """Build canonical ``(value,T,T,T)`` using the cheapest exact route.

    Most helper columns are solid S/P towers or one-generation S/c scaffolds;
    sending them through the general Corner compiler creates an avoidable
    quadratic family of subproofs.  Only genuinely structured columns fall
    back to the Corner theorem constructor.
    """
    if natural_only and analyze_column(value).route is Route.EVENT:
        raise ProofDagError(f"event-route child in natural proof: {value!r}")
    tower_height = max(1, len(value))
    rows = [
        [
            value[l] if l < len(value) else EMPTY,
            ORDINARY if l < tower_height else EMPTY,
            ORDINARY if l < tower_height else EMPTY,
            ORDINARY if l < tower_height else EMPTY,
        ]
        for l in range(cap)
    ]
    target = code(rows)
    chars = {cell for row in rows for cell in row if cell != EMPTY}
    try:
        if chars <= {ORDINARY}:
            return s_only_shape_proof(target, cap)
        if chars <= {ORDINARY, PIN}:
            return sp_only_shape_proof(target, cap)
        if chars <= {ORDINARY, "c"}:
            return generated_solid_shape_proof(target, cap)
    except ProofDagError:
        pass
    return corner_raw_proof(value, cap)


@lru_cache(maxsize=None)
def half_from_corner_proofs(left: str, right: str, cap: int, natural_only: bool = False) -> ProofNode:
    if natural_only:
        for value in (left, right):
            if analyze_column(value).route is Route.EVENT:
                raise ProofDagError(f"event-route child in natural half: {value!r}")
    left_full = canonical_column_proof(left, cap, natural_only)
    right_full = canonical_column_proof(right, cap, natural_only)
    fixture_v = cut_proof(right_full, "east")          # (v,T)
    fixture_u = cut_proof(rotate_proof(left_full, 1), "east")  # (T,u)
    fixture_u_west = rotate_proof(fixture_u, 2)
    joined = swap_proof(fixture_v, fixture_u_west, 0)  # (v,T,T,u)
    oriented = rotate_proof(joined, 1)                 # (u,v,T,T)
    east = cut_proof(oriented, "east")
    rows = _rows(east.result, cap)
    actual = (column(rows, 0), column(rows, 1))
    if actual != (left, right):
        raise ProofDagError(("half proof output", actual, (left, right), east.result))
    return east


def _prove_shape_uncached(target: str, cap: int, natural_only: bool) -> ProofNode:
    normalized = code(_rows(target, cap))
    rows = _rows(normalized, cap)
    if not normalized:
        return empty_shape_proof(cap)
    chars = {cell for row in rows for cell in row if cell != EMPTY}
    if chars <= {ORDINARY}:
        return s_only_shape_proof(normalized, cap)
    if chars <= {ORDINARY, PIN}:
        return sp_only_shape_proof(normalized, cap)
    if chars <= {ORDINARY, "c"}:
        try:
            return generated_solid_shape_proof(normalized, cap)
        except ProofDagError:
            pass

    oriented = _rotate_to_east(normalized, cap)
    if oriented is not None:
        east_code, k = oriented
        east_rows = _rows(east_code, cap)
        left, right = column(east_rows, 0), column(east_rows, 1)
        if is_stable(east_rows):
            # Natural Corner C1-C6 is proved before the general Half theorem.
            # Its helper halves must therefore be solid direct-prefab halves.
            # C7 natural-half assembly calls half_from_corner_proofs directly
            # after the Natural Corner stage and does not pass through here.
            if natural_only and (EMPTY in left or EMPTY in right):
                raise ProofDagError(
                    "natural Corner attempted a non-solid Half dependency: "
                    f"{left!r}, {right!r}"
                )
            base = half_from_corner_proofs(left, right, cap, natural_only)
            # base is in the rotated orientation. Undo target->east rotation.
            result = rotate_proof(base, (-k) % 4)
            if result.result == normalized:
                return result
    raise ProofDagError(f"no raw proof strategy for operand {normalized!r}")


def shape_raw_proof(target: str, cap: int, natural_only: bool = False) -> ProofNode:
    key = (code(_rows(target, cap)), cap, natural_only)
    cached = _SHAPE_CACHE.get(key)
    if cached is not None:
        return cached
    if key in _BUILDING_SHAPE:
        raise ProofDagError(f"shape proof cycle: {key}")
    _BUILDING_SHAPE.add(key)
    try:
        result = _prove_shape_uncached(key[0], cap, natural_only)
        _SHAPE_CACHE[key] = result
        return result
    finally:
        _BUILDING_SHAPE.remove(key)


_SHAPE_CACHE: dict[tuple[str, int, bool], ProofNode] = {}
_CORNER_CACHE: dict[tuple[str, int], ProofNode] = {}


def _apply_recorded_operation(current: ProofNode, step) -> ProofNode:
    """Attach a recorded exact edge without executing it a second time.

    ``replay_corner_full`` has already produced ``before``/``after`` using the
    structural kernel.  The independent :func:`verify_proof` later re-executes
    every node once, so construction itself only needs to attach children.
    """
    cap = current.cap
    operation = step.operation
    result = step.after
    if operation.startswith("rotate_cw") or operation == "rotate_cw":
        return ProofNode("ROTATE", cap, result, (current,), 1)
    if operation.startswith("rotate_ccw") or operation == "rotate_ccw":
        return ProofNode("ROTATE", cap, result, (current,), 3)
    if operation == "C3_generate":
        return ProofNode("GENERATE", cap, result, (current,))
    if operation in ("C6_typed_push", "C7_overflow_event"):
        return ProofNode("PIN_PUSH", cap, result, (current,))
    if operation in ("C4_shatter", "C5_pin_cut_descent"):
        return ProofNode("CUT", cap, result, (current,), "east")
    if operation in ("C1_top_deposit", "C2_anchored_deposit"):
        operand = shape_raw_proof(step.operand, cap, natural_only=True)
        return ProofNode("STACK", cap, result, (current, operand))
    if operation.startswith("swap_"):
        operand = shape_raw_proof(step.operand, cap, natural_only=True)
        return ProofNode("SWAP", cap, result, (current, operand), 0)
    raise ProofDagError(f"unsupported recorded operation {operation!r}")


def _c7_predecessor_raw_proof(column_value: str, cap: int) -> ProofNode:
    from .corner_constructor import construct_corner
    cert = construct_corner(column_value, cap)
    if cert.event is None:
        raise ProofDagError("C7 proof requested for non-event Corner")
    a, b, c, d = cert.event.c7.predecessor_columns
    bc = half_from_corner_proofs(b, c, cap, True)
    da_east = half_from_corner_proofs(d, a, cap, True)
    da_west = rotate_proof(da_east, 2)
    joined = swap_proof(bc, da_west, 0)  # (B,C,D,A)
    final = rotate_proof(joined, 1)      # (A,B,C,D)
    if final.result != cert.event.c7.predecessor:
        raise ProofDagError(("C7 predecessor proof", final.result, cert.event.c7.predecessor))
    return final


def corner_raw_proof(column_value: str, cap: int | None = None) -> ProofNode:
    normalized = column_value.rstrip(EMPTY)
    if cap is None:
        cap = max(1, len(normalized))
    key = (normalized, cap)
    cached = _CORNER_CACHE.get(key)
    if cached is not None:
        return cached
    if key in _BUILDING_CORNER:
        raise ProofDagError(f"Corner proof cycle: {key}")
    _BUILDING_CORNER.add(key)
    try:
        replay = replay_corner_full(normalized, cap, False)
        if not replay.replay_ok:
            raise ProofDagError("compact full replay failed")
        if not replay.operations:
            # The empty target canonical shape is still -SSS, not empty.
            current = shape_raw_proof(replay.final_full_shape, cap, True)
        else:
            current = shape_raw_proof(replay.operations[0].before, cap, True)
            for step in replay.operations:
                if step.operation == "C7_assemble_from_BC_DA":
                    current = _c7_predecessor_raw_proof(normalized, cap)
                else:
                    if current.result != step.before:
                        raise ProofDagError(("recorded before mismatch", step.operation, current.result, step.before))
                    current = _apply_recorded_operation(current, step)
                if current.result != step.after:
                    raise ProofDagError(("recorded after mismatch", step.operation, current.result, step.after))
        if current.result != replay.final_full_shape:
            raise ProofDagError(("Corner final full", current.result, replay.final_full_shape))
        rows = _rows(current.result, cap)
        if column(rows, 0) != normalized:
            raise ProofDagError(("Corner final column", column(rows, 0), normalized))
        _CORNER_CACHE[key] = current
        return current
    finally:
        _BUILDING_CORNER.remove(key)


def half_raw_proof(code_value: str, layers: int | None = None) -> ProofNode:
    from .half_family import analyze_half
    analysis = analyze_half(code_value, layers)
    if not analysis.buildable:
        raise ProofDagError("half is not buildable")
    result = half_from_corner_proofs(analysis.left_column, analysis.right_column, analysis.cap, False)
    if result.result != analysis.normalized_code:
        raise ProofDagError(("Half final", result.result, analysis.normalized_code))
    return result



def clear_proof_caches() -> None:
    """Release memoized proof DAGs between large independent audit batches."""
    _SHAPE_CACHE.clear()
    _CORNER_CACHE.clear()
    for fn in (
        raw_input_proof, single_cell_proof, empty_shape_proof,
        single_layer_s_pattern_proof, s_only_shape_proof, one_pin_proof,
        single_layer_sp_proof, sp_only_shape_proof,
        generated_solid_shape_proof, canonical_column_proof, half_from_corner_proofs,
    ):
        fn.cache_clear()
    _rows.cache_clear()


def verify_proof_forest(roots: Sequence[ProofNode]) -> ProofForestAudit:
    """Independently replay a forest while sharing common subproofs once."""
    roots = tuple(roots)
    state: dict[int, int] = {}  # 0 unseen, 1 visiting, 2 verified
    postorder: list[ProofNode] = []

    for root in roots:
        traversal: list[tuple[ProofNode, bool]] = [(root, False)]
        while traversal:
            node, exiting = traversal.pop()
            ident = id(node)
            if exiting:
                state[ident] = 2
                postorder.append(node)
                continue
            status = state.get(ident, 0)
            if status == 2:
                continue
            if status == 1:
                raise ProofDagError("cycle in proof DAG")
            state[ident] = 1
            traversal.append((node, True))
            for child in reversed(node.children):
                child_state = state.get(id(child), 0)
                if child_state == 1:
                    raise ProofDagError("cycle in proof DAG")
                if child_state != 2:
                    traversal.append((child, False))

    result_cache: dict[int, str] = {}
    depth_cache: dict[int, int] = {}
    operation_nodes = 0
    raw_leaves = 0
    edges = 0
    all_stable = True

    for node in postorder:
        child_results = [result_cache[id(child)] for child in node.children]
        edges += len(node.children)
        if node.operation == "RAW_INPUT":
            if child_results or node.result != code(input_full()):
                raise ProofDagError("invalid raw leaf")
            expected = node.result
            raw_leaves += 1
        elif node.operation == "ROTATE":
            expected = code(rotate(_rows(child_results[0], node.cap), int(node.parameter)))
        elif node.operation == "CUT":
            east, west = cut(_rows(child_results[0], node.cap), node.cap)
            expected = code(east if node.parameter == "east" else west)
        elif node.operation == "SWAP":
            outputs = swap(
                _rows(child_results[0], node.cap),
                _rows(child_results[1], node.cap),
                node.cap,
            )
            expected = code(outputs[int(node.parameter)])
        elif node.operation == "STACK":
            expected = code(
                stack(
                    _rows(child_results[0], node.cap),
                    _rows(child_results[1], node.cap),
                    node.cap,
                )
            )
        elif node.operation == "GENERATE":
            expected = code(generate(_rows(child_results[0], node.cap), node.cap))
        elif node.operation == "PIN_PUSH":
            expected = code(push_pin(_rows(child_results[0], node.cap), node.cap))
        else:
            raise ProofDagError(f"unknown proof op {node.operation}")

        if expected != node.result:
            raise ProofDagError(
                ("proof replay mismatch", node.operation, expected, node.result)
            )
        if node.result and not is_stable(_rows(node.result, node.cap)):
            all_stable = False
            raise ProofDagError(("unstable proof node", node.operation, node.result))

        result_cache[id(node)] = node.result
        depth_cache[id(node)] = 1 + max(
            (depth_cache[id(child)] for child in node.children), default=0
        )
        operation_nodes += node.operation != "RAW_INPUT"

    results = tuple(result_cache[id(root)] for root in roots)
    return ProofForestAudit(
        results=results,
        unique_nodes=len(postorder),
        operation_nodes=operation_nodes,
        raw_leaves=raw_leaves,
        edges=edges,
        max_depth=max((depth_cache[id(root)] for root in roots), default=0),
        all_stable=all_stable,
        replay_ok=all(result == root.result for result, root in zip(results, roots)),
    )


def verify_proof(root: ProofNode) -> ProofAudit:
    """Independently replay one complete raw-operation proof DAG."""
    forest = verify_proof_forest((root,))
    return ProofAudit(
        result=forest.results[0],
        unique_nodes=forest.unique_nodes,
        operation_nodes=forest.operation_nodes,
        raw_leaves=forest.raw_leaves,
        max_depth=forest.max_depth,
        all_stable=forest.all_stable,
        replay_ok=forest.replay_ok,
    )


__all__ = [
    "ProofNode", "ProofAudit", "ProofForestAudit", "ProofDagError",
    "verify_proof", "verify_proof_forest",
    "raw_input_proof", "single_cell_proof", "single_layer_s_pattern_proof",
    "one_pin_proof", "shape_raw_proof", "corner_raw_proof", "half_raw_proof",
    "canonical_column_proof", "half_from_corner_proofs", "clear_proof_caches",
]
