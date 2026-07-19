from __future__ import annotations

import contextlib
import heapq
import io
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy_corner_recipe import (  # noqa: E402
    TARGET_CODE,
    TARGET_LEFT_PILLAR,
    Shape,
    rotate,
    structural,
)

with contextlib.redirect_stdout(io.StringIO()):
    from corner_tracer import build_pinable_shape  # noqa: E402


@dataclass(frozen=True)
class Aux:
    name: str
    code: str
    proof_kind: str


@dataclass
class Node:
    code: str
    path: list[dict]
    depth: int


def from_struct(code: str) -> Shape:
    shape = Shape.from_string(code)
    shape.max_layers = len(TARGET_LEFT_PILLAR)
    return shape


def rows(code: str) -> list[str]:
    return code.split(":") if code else []


def distance_parts(code: str, goal: str) -> dict[str, int]:
    ar = rows(code)
    br = rows(goal)
    n = max(len(ar), len(br))
    mismatch = unwanted_p = missing_crystal = unwanted_crystal = missing_s = 0
    for i in range(n):
        a = ar[i] if i < len(ar) else "----"
        b = br[i] if i < len(br) else "----"
        for x, y in zip(a, b):
            if x != y:
                mismatch += 1
                if x == "P":
                    unwanted_p += 1
                if y == "c" and x != "c":
                    missing_crystal += 1
                if x == "c" and y != "c":
                    unwanted_crystal += 1
                if y == "S" and x != "S":
                    missing_s += 1
    return {
        "mismatch": mismatch,
        "unwanted_p": unwanted_p,
        "missing_crystal": missing_crystal,
        "unwanted_crystal": unwanted_crystal,
        "missing_s": missing_s,
    }


def score(code: str, goal: str, depth: int) -> tuple[int, int, int, int]:
    d = distance_parts(code, goal)
    weighted = (
        d["mismatch"]
        + 3 * d["missing_crystal"]
        + 2 * d["unwanted_crystal"]
        + d["unwanted_p"]
        + depth
    )
    return weighted, d["mismatch"], d["unwanted_p"], len(code)


def stable(shape: Shape) -> Shape:
    out = shape.apply_physics()
    out.max_layers = len(TARGET_LEFT_PILLAR)
    return out


def add_aux(pool: dict[str, Aux], name: str, shape: Shape, proof_kind: str) -> None:
    shape.max_layers = len(TARGET_LEFT_PILLAR)
    out = stable(shape)
    code = structural(out)
    if code and code not in pool:
        pool[code] = Aux(name, code, proof_kind)


def build_auxiliaries(pin_result: Shape, predecessor: Shape, target: Shape) -> list[Aux]:
    cap = len(TARGET_LEFT_PILLAR)
    pool: dict[str, Aux] = {}

    # Raw ordinary pieces, solid columns/halves, and single-layer masks are
    # independently simple inputs. They are the safest helpers for discovery.
    for mask in range(1, 16):
        row = "".join("S" if mask & (1 << q) else "-" for q in range(4))
        add_aux(pool, f"ONE_LAYER_{mask:02x}", from_struct(row), "simple-input")
        add_aux(pool, f"SOLID_{mask:02x}", from_struct(":".join(row for _ in range(cap))), "simple-no-crystal")

    target_rows = rows(structural(target))
    for mask in (1, 2, 4, 8, 3, 6, 12, 9):
        ordinary_rows = []
        for row in target_rows:
            ordinary_rows.append(
                "".join(
                    ("S" if row[q] != "-" else "-") if mask & (1 << q) else "-"
                    for q in range(4)
                )
            )
        add_aux(pool, f"TARGET_ORDINARY_MASK_{mask:02x}", from_struct(":".join(ordinary_rows)), "simple-no-crystal")

    # Already certified/generated shapes from the legacy Corner path.
    add_aux(pool, "LEGACY_PREDECESSOR", predecessor, "legacy-corner-constructor")
    add_aux(pool, "LEGACY_PIN_RESULT", pin_result, "legacy-corner+pin")

    # Every cutter output of a known buildable shape remains buildable.
    for base_name, base in (("PRED", predecessor), ("PIN", pin_result)):
        for turns in range(4):
            rotated = rotate(base, turns)
            for kind, pieces in (
                ("SC", rotated.simple_cutter()),
                ("HC", rotated.half_cutter()),
                ("QC", rotated.quad_cutter()),
            ):
                for index, piece in enumerate(pieces):
                    add_aux(pool, f"{base_name}_R{turns}_{kind}{index}", piece, "cut-from-certified")

    return sorted(pool.values(), key=lambda x: (x.proof_kind, x.name, x.code))


def unique_rotations(shape: Shape) -> list[tuple[int, Shape]]:
    result = []
    seen = set()
    for turns in range(4):
        candidate = rotate(shape, turns)
        code = structural(candidate)
        if code not in seen:
            seen.add(code)
            result.append((turns, candidate))
    return result


def cutter_successors(node: Node) -> list[Node]:
    shape = from_struct(node.code)
    out: list[Node] = []
    seen = set()
    for pre_turns, rotated in unique_rotations(shape):
        for kind, pieces in (
            ("SIMPLE_CUT", rotated.simple_cutter()),
            ("HALF_CUT", rotated.half_cutter()),
            ("QUAD_CUT", rotated.quad_cutter()),
        ):
            for index, piece in enumerate(pieces):
                for post_turns, candidate in unique_rotations(piece):
                    code = structural(candidate)
                    if not code or code in seen:
                        continue
                    seen.add(code)
                    out.append(
                        Node(
                            code,
                            node.path
                            + [
                                {
                                    "op": kind,
                                    "pre_turns": pre_turns,
                                    "output": index,
                                    "post_turns": post_turns,
                                }
                            ],
                            node.depth + 1,
                        )
                    )
    return out


def unary_successors(node: Node) -> list[Node]:
    shape = from_struct(node.code)
    out: list[Node] = []

    pushed = shape.push_pin()
    pushed_code = structural(pushed)
    if pushed_code and pushed_code != node.code:
        out.append(Node(pushed_code, node.path + [{"op": "PIN_PUSH"}], node.depth + 1))

    # Generator is included because it is the only primitive that can create
    # crystals from empty/P cells. Final acceptance still requires exact replay.
    generated = shape.crystal_generator("y")
    generated_code = structural(generated)
    if generated_code and generated_code != node.code:
        out.append(Node(generated_code, node.path + [{"op": "CRYSTAL_GENERATOR"}], node.depth + 1))

    out.extend(cutter_successors(node))
    return out


def binary_successors(node: Node, auxiliaries: list[Aux], aux_rotation_cache: dict[str, list[tuple[int, Shape]]]) -> list[Node]:
    current = from_struct(node.code)
    out: list[Node] = []
    local_seen = set()

    # Prefer helpers whose structural distance to the target-relevant state is
    # small; the caller passes an already limited pool.
    for current_turns, a in unique_rotations(current):
        for aux in auxiliaries:
            for aux_turns, b in aux_rotation_cache[aux.code]:
                swap_outputs = Shape.swap(a, b)
                for output_index, output in enumerate(swap_outputs):
                    for final_turns, candidate in unique_rotations(output):
                        code = structural(candidate)
                        if not code or code in local_seen:
                            continue
                        local_seen.add(code)
                        out.append(
                            Node(
                                code,
                                node.path
                                + [
                                    {
                                        "op": "SWAP",
                                        "current_turns": current_turns,
                                        "aux": aux.name,
                                        "aux_proof": aux.proof_kind,
                                        "aux_turns": aux_turns,
                                        "output": output_index,
                                        "final_turns": final_turns,
                                    }
                                ],
                                node.depth + 1,
                            )
                        )

                for order, stacked in (
                    ("CURRENT_BOTTOM", Shape.stack(a, b)),
                    ("AUX_BOTTOM", Shape.stack(b, a)),
                ):
                    for final_turns, candidate in unique_rotations(stacked):
                        code = structural(candidate)
                        if not code or code in local_seen:
                            continue
                        local_seen.add(code)
                        out.append(
                            Node(
                                code,
                                node.path
                                + [
                                    {
                                        "op": "STACK",
                                        "order": order,
                                        "current_turns": current_turns,
                                        "aux": aux.name,
                                        "aux_proof": aux.proof_kind,
                                        "aux_turns": aux_turns,
                                        "final_turns": final_turns,
                                    }
                                ],
                                node.depth + 1,
                            )
                        )
    return out


def best_first_search(
    *,
    max_depth: int = 4,
    beam_width: int = 100,
    auxiliary_limit: int = 36,
    state_limit: int = 20000,
    max_seconds: float = 80.0,
) -> dict:
    start_time = time.perf_counter()
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap

    with contextlib.redirect_stdout(io.StringIO()):
        predecessor = from_struct(build_pinable_shape(TARGET_LEFT_PILLAR))
    pin_result = predecessor.push_pin()
    target = from_struct(TARGET_CODE)
    goal = structural(target)

    all_aux = build_auxiliaries(pin_result, predecessor, target)
    # Rank helpers by their own distance to the goal and proof simplicity.
    proof_rank = {"simple-input": 0, "simple-no-crystal": 1, "cut-from-certified": 2, "legacy-corner-constructor": 3, "legacy-corner+pin": 4}
    all_aux.sort(key=lambda a: (proof_rank.get(a.proof_kind, 9), score(a.code, goal, 0), a.name))
    auxiliaries = all_aux[:auxiliary_limit]
    aux_rotation_cache = {aux.code: unique_rotations(from_struct(aux.code)) for aux in auxiliaries}

    start = Node(
        structural(pin_result),
        [{"op": "BUILD_LEGACY_CORNER_PREDECESSOR", "result": structural(predecessor)}, {"op": "PIN_PUSH"}],
        0,
    )

    # Critical correction versus the first search: cutter outputs are actual
    # frontier seeds, not diagnostics only.
    initial_nodes = [start] + cutter_successors(start)
    seen_depth: dict[str, int] = {}
    frontier = []
    serial = 0
    for node in initial_nodes:
        previous = seen_depth.get(node.code)
        if previous is None or node.depth < previous:
            seen_depth[node.code] = node.depth
            heapq.heappush(frontier, (score(node.code, goal, node.depth), serial, node))
            serial += 1

    best_by_code: dict[str, Node] = {}
    expanded = 0
    generated = 0
    depth_histogram: dict[int, int] = {}
    hit = None
    stop_reason = "frontier-exhausted"

    while frontier:
        if time.perf_counter() - start_time > max_seconds:
            stop_reason = "time-limit"
            break
        if expanded >= state_limit:
            stop_reason = "state-limit"
            break

        batch: list[Node] = []
        while frontier and len(batch) < beam_width:
            _priority, _serial, node = heapq.heappop(frontier)
            if seen_depth.get(node.code) != node.depth:
                continue
            batch.append(node)

        if not batch:
            break

        next_candidates: dict[str, Node] = {}
        for node in batch:
            expanded += 1
            depth_histogram[node.depth] = depth_histogram.get(node.depth, 0) + 1
            best_by_code.setdefault(node.code, node)
            if node.code == goal:
                hit = node
                stop_reason = "hit"
                break
            if node.depth >= max_depth:
                continue

            successors = unary_successors(node)
            # Binary expansion is expensive. Apply it to states within a useful
            # heuristic band or to the known cutter/P-heavy near-goal family.
            parts = distance_parts(node.code, goal)
            if parts["mismatch"] <= 18 or node.depth <= 1:
                successors.extend(binary_successors(node, auxiliaries, aux_rotation_cache))

            generated += len(successors)
            for child in successors:
                old_depth = seen_depth.get(child.code)
                if old_depth is not None and old_depth <= child.depth:
                    continue
                seen_depth[child.code] = child.depth
                old = next_candidates.get(child.code)
                if old is None or score(child.code, goal, child.depth) < score(old.code, goal, old.depth):
                    next_candidates[child.code] = child

            if time.perf_counter() - start_time > max_seconds:
                stop_reason = "time-limit"
                break

        if hit is not None or stop_reason == "time-limit":
            break

        ranked = sorted(next_candidates.values(), key=lambda n: (score(n.code, goal, n.depth), len(n.path), n.code))
        for node in ranked[: beam_width * 4]:
            heapq.heappush(frontier, (score(node.code, goal, node.depth), serial, node))
            serial += 1

    candidates = list(best_by_code.values())
    candidates.extend(node for _p, _s, node in frontier[: beam_width * 4])
    unique = {}
    for node in sorted(candidates, key=lambda n: (score(n.code, goal, n.depth), len(n.path), n.code)):
        unique.setdefault(node.code, node)
    closest = []
    for node in list(unique.values())[:20]:
        closest.append(
            {
                "score": score(node.code, goal, node.depth),
                "distance": distance_parts(node.code, goal),
                "code": node.code,
                "depth": node.depth,
                "path": node.path,
            }
        )

    return {
        "schema_version": 1,
        "goal": goal,
        "start": start.code,
        "parameters": {
            "max_depth": max_depth,
            "beam_width": beam_width,
            "auxiliary_limit": auxiliary_limit,
            "state_limit": state_limit,
            "max_seconds": max_seconds,
        },
        "auxiliaries": [asdict(aux) for aux in auxiliaries],
        "expanded": expanded,
        "generated": generated,
        "seen": len(seen_depth),
        "depth_histogram": depth_histogram,
        "elapsed_seconds": time.perf_counter() - start_time,
        "stop_reason": stop_reason,
        "hit": None if hit is None else {"code": hit.code, "depth": hit.depth, "path": hit.path},
        "closest": closest,
    }


if __name__ == "__main__":
    print(json.dumps(best_first_search(), ensure_ascii=False, indent=2))
