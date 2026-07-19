from __future__ import annotations

import heapq
import json
import time
from dataclasses import dataclass

from search_family_macro import (
    Helper,
    Node,
    build_helper_pool,
    current_unary,
    distance,
    family_code,
    from_struct,
    score,
    stable,
    structural,
    unique_rotations,
    Shape,
)


@dataclass(frozen=True)
class RotatedHelper:
    helper: Helper
    turns: int
    code: str
    shape: Shape
    layers: int
    crystal_count: int
    pin_count: int
    occupied_mask: int


def padded_rows(code: str, cap: int) -> list[str]:
    parts = code.split(":") if code else []
    return (parts + ["----"] * cap)[:cap]


def helper_index(helpers: list[Helper], cap: int) -> list[RotatedHelper]:
    out: list[RotatedHelper] = []
    seen = set()
    for helper in helpers:
        shape = from_struct(helper.code, cap)
        for turns, rotated in unique_rotations(shape):
            code = structural(stable(rotated, cap))
            key = (helper.code, code)
            if not code or key in seen:
                continue
            seen.add(key)
            rows = padded_rows(code, cap)
            occupied_mask = 0
            crystal_count = pin_count = 0
            for row in rows:
                for q, ch in enumerate(row):
                    if ch != "-":
                        occupied_mask |= 1 << q
                    crystal_count += ch == "c"
                    pin_count += ch == "P"
            out.append(
                RotatedHelper(
                    helper=helper,
                    turns=turns,
                    code=code,
                    shape=from_struct(code, cap),
                    layers=len(code.split(":")) if code else 0,
                    crystal_count=int(crystal_count),
                    pin_count=int(pin_count),
                    occupied_mask=occupied_mask,
                )
            )
    return out


def mismatch_profile(current_code: str, goal_code: str, cap: int) -> dict:
    current = padded_rows(current_code, cap)
    goal = padded_rows(goal_code, cap)
    mismatches = []
    missing_crystals = []
    missing_s = []
    wrong_cells = []
    mismatch_columns = set()
    for layer, (a, b) in enumerate(zip(current, goal)):
        for q, (x, y) in enumerate(zip(a, b)):
            if x == y:
                continue
            mismatches.append((layer, q, x, y))
            mismatch_columns.add(q)
            wrong_cells.append((layer, q))
            if y == "c":
                missing_crystals.append((layer, q))
            if y == "S":
                missing_s.append((layer, q))
    return {
        "mismatches": mismatches,
        "mismatch_columns": mismatch_columns,
        "missing_crystals": missing_crystals,
        "missing_s": missing_s,
        "wrong_cells": wrong_cells,
        "current": current,
        "goal": goal,
    }


def helper_relevance(rotated: RotatedHelper, profile: dict, cap: int) -> tuple:
    rows = padded_rows(rotated.code, cap)
    match_needed = 0
    wrong_at_needed = 0
    damage_matched = 0
    crystal_match = 0
    support_match = 0

    mismatch_set = {(l, q) for l, q, _x, _y in profile["mismatches"]}
    for layer, q, _x, target in profile["mismatches"]:
        h = rows[layer][q]
        if h == target:
            match_needed += 1
            crystal_match += target == "c"
            support_match += target == "S"
        elif h != "-":
            wrong_at_needed += 1

    # Helpers that inject many pieces into already-correct target cells tend to
    # create huge unproductive branches. Sample the full matched region once.
    for layer in range(cap):
        for q in range(4):
            if (layer, q) in mismatch_set:
                continue
            if rows[layer][q] != "-" and rows[layer][q] != profile["goal"][layer][q]:
                damage_matched += 1

    need_c = len(profile["missing_crystals"])
    crystal_distance = abs(rotated.crystal_count - need_c)
    proof_cost = len(rotated.helper.proof)
    return (
        -(8 * crystal_match + 3 * support_match + 2 * match_needed),
        3 * wrong_at_needed + damage_matched,
        crystal_distance,
        proof_cost,
        rotated.layers,
        rotated.code,
    )


def select_helpers(index: list[RotatedHelper], current_code: str, goal_code: str, cap: int, limit: int) -> list[RotatedHelper]:
    profile = mismatch_profile(current_code, goal_code, cap)
    ranked = sorted(index, key=lambda h: helper_relevance(h, profile, cap))

    selected = []
    selected_codes = set()
    need_crystal = bool(profile["missing_crystals"])
    mismatch_mask = sum(1 << q for q in profile["mismatch_columns"])
    for helper in ranked:
        if helper.code in selected_codes:
            continue
        if mismatch_mask and not (helper.occupied_mask & mismatch_mask):
            continue
        if need_crystal and not helper.crystal_count and len(selected) < max(2, limit // 3):
            continue
        selected.append(helper)
        selected_codes.add(helper.code)
        if len(selected) >= limit:
            break

    # Always retain a few no-crystal structural helpers because they can remove
    # pins/scaffolds while preserving crystals in the current shape.
    if need_crystal:
        for helper in ranked:
            if helper.code in selected_codes or helper.crystal_count:
                continue
            if mismatch_mask and not (helper.occupied_mask & mismatch_mask):
                continue
            selected.append(helper)
            selected_codes.add(helper.code)
            if len(selected) >= limit + 3:
                break
    return selected


class TopK:
    def __init__(self, limit: int, goal: str, cap: int):
        self.limit = limit
        self.goal = goal
        self.cap = cap
        self.by_code: dict[str, Node] = {}

    def add(self, node: Node) -> bool:
        old = self.by_code.get(node.code)
        if old is not None and (old.depth, len(old.path)) <= (node.depth, len(node.path)):
            return False
        self.by_code[node.code] = node
        if len(self.by_code) > self.limit * 3:
            ranked = sorted(
                self.by_code.values(),
                key=lambda n: (score(n.code, self.goal, self.cap, n.depth), len(n.path), n.code),
            )[: self.limit]
            self.by_code = {n.code: n for n in ranked}
        return True

    def values(self) -> list[Node]:
        return sorted(
            self.by_code.values(),
            key=lambda n: (score(n.code, self.goal, self.cap, n.depth), len(n.path), n.code),
        )[: self.limit]


def binary_stream(
    node: Node,
    helpers: list[RotatedHelper],
    goal: str,
    cap: int,
    top_limit: int,
) -> tuple[list[Node], int, int, int]:
    current = from_struct(node.code, cap)
    collector = TopK(top_limit, goal, cap)
    generated = symmetry_prunes = no_op_prunes = 0
    output_seen = set()

    for current_turns, a in unique_rotations(current):
        for rotated in helpers:
            b = rotated.shape
            pair_key = tuple(sorted((structural(a), rotated.code)))

            for index, output in enumerate(Shape.swap(a, b)):
                generated += 1
                for final_turns, candidate in unique_rotations(output):
                    code = structural(stable(candidate, cap))
                    if not code or code == node.code:
                        no_op_prunes += 1
                        continue
                    if code in output_seen:
                        symmetry_prunes += 1
                        continue
                    output_seen.add(code)
                    collector.add(
                        Node(
                            code,
                            node.path
                            + [
                                {
                                    "op": "SWAP",
                                    "current_turns": current_turns,
                                    "helper": rotated.helper.name,
                                    "helper_code": rotated.helper.code,
                                    "helper_proof": list(rotated.helper.proof),
                                    "helper_turns": rotated.turns,
                                    "output": index,
                                    "final_turns": final_turns,
                                    "pair_key": pair_key,
                                }
                            ],
                            node.depth + 1,
                        )
                    )
                    if code == goal:
                        return [collector.by_code[code]], generated, symmetry_prunes, no_op_prunes

            # Stack is ordered; evaluate both orders, but output interning removes
            # commutative coincidences immediately.
            for order, output in (
                ("CURRENT_BOTTOM", Shape.stack(a, b)),
                ("HELPER_BOTTOM", Shape.stack(b, a)),
            ):
                generated += 1
                for final_turns, candidate in unique_rotations(output):
                    code = structural(stable(candidate, cap))
                    if not code or code == node.code:
                        no_op_prunes += 1
                        continue
                    if code in output_seen:
                        symmetry_prunes += 1
                        continue
                    output_seen.add(code)
                    collector.add(
                        Node(
                            code,
                            node.path
                            + [
                                {
                                    "op": "STACK",
                                    "order": order,
                                    "current_turns": current_turns,
                                    "helper": rotated.helper.name,
                                    "helper_code": rotated.helper.code,
                                    "helper_proof": list(rotated.helper.proof),
                                    "helper_turns": rotated.turns,
                                    "final_turns": final_turns,
                                }
                            ],
                            node.depth + 1,
                        )
                    )
                    if code == goal:
                        return [collector.by_code[code]], generated, symmetry_prunes, no_op_prunes

    return collector.values(), generated, symmetry_prunes, no_op_prunes


def search_macro_v2(
    repeats: int = 1,
    *,
    max_depth: int = 7,
    beam_width: int = 96,
    helper_limit_per_state: int = 12,
    max_seconds: float = 110.0,
    state_limit: int = 40000,
) -> dict:
    started = time.perf_counter()
    cap = 1 + 5 * (repeats + 1)
    Shape.MAX_LAYERS = cap
    start_code = structural(stable(from_struct(family_code(repeats), cap), cap))
    goal_code = structural(stable(from_struct(family_code(repeats + 1), cap), cap))

    helper_pool = build_helper_pool(cap, max_depth=2, max_helpers=1200)
    index = helper_index(helper_pool, cap)

    start = Node(start_code, [], 0)
    queue = [(score(start.code, goal_code, cap, 0), 0, start)]
    serial = 1
    seen_depth = {start.code: 0}
    expanded = generated = 0
    symmetry_prunes = no_op_prunes = 0
    helper_selection_total = 0
    depth_histogram: dict[int, int] = {}
    closest_by_code = {start.code: start}
    hit = None
    stop_reason = "frontier-exhausted"

    while queue:
        if time.perf_counter() - started >= max_seconds:
            stop_reason = "time-limit"
            break
        if expanded >= state_limit:
            stop_reason = "state-limit"
            break

        batch = []
        while queue and len(batch) < beam_width:
            _priority, _serial, node = heapq.heappop(queue)
            if seen_depth.get(node.code) != node.depth:
                continue
            batch.append(node)
        if not batch:
            break

        next_top = TopK(beam_width * 4, goal_code, cap)
        for node in batch:
            expanded += 1
            depth_histogram[node.depth] = depth_histogram.get(node.depth, 0) + 1
            closest_by_code.setdefault(node.code, node)
            if node.code == goal_code:
                hit = node
                stop_reason = "hit"
                break
            if node.depth >= max_depth:
                continue

            for child in current_unary(node, cap):
                generated += 1
                if child.code == goal_code:
                    hit = child
                    stop_reason = "hit"
                    break
                old = seen_depth.get(child.code)
                if old is None or child.depth < old:
                    seen_depth[child.code] = child.depth
                    next_top.add(child)
            if hit is not None:
                break

            profile = distance(node.code, goal_code, cap)
            if node.depth <= 3 or profile["mismatch"] <= 18:
                selected = select_helpers(index, node.code, goal_code, cap, helper_limit_per_state)
                helper_selection_total += len(selected)
                children, gen, sym, nop = binary_stream(
                    node,
                    selected,
                    goal_code,
                    cap,
                    top_limit=max(beam_width, 128),
                )
                generated += gen
                symmetry_prunes += sym
                no_op_prunes += nop
                for child in children:
                    if child.code == goal_code:
                        hit = child
                        stop_reason = "hit"
                        break
                    old = seen_depth.get(child.code)
                    if old is None or child.depth < old:
                        seen_depth[child.code] = child.depth
                        next_top.add(child)
                if hit is not None:
                    break

            if time.perf_counter() - started >= max_seconds:
                stop_reason = "time-limit"
                break

        if hit is not None or stop_reason == "time-limit":
            break

        for child in next_top.values():
            heapq.heappush(queue, (score(child.code, goal_code, cap, child.depth), serial, child))
            serial += 1

    candidates = list(closest_by_code.values()) + [node for _p, _s, node in queue[: beam_width * 4]]
    unique = {}
    for node in sorted(candidates, key=lambda n: (score(n.code, goal_code, cap, n.depth), len(n.path), n.code)):
        unique.setdefault(node.code, node)
    closest = []
    for node in list(unique.values())[:12]:
        closest.append(
            {
                "score": score(node.code, goal_code, cap, node.depth),
                "distance": distance(node.code, goal_code, cap),
                "code": node.code,
                "depth": node.depth,
                "path": node.path,
            }
        )

    return {
        "schema_version": 2,
        "family": "F_n = SS-- + (SS--,-S--,SS--,-S--,cS--)^n",
        "repeats": repeats,
        "cap": cap,
        "start": start_code,
        "goal": goal_code,
        "helper_pool": len(helper_pool),
        "rotated_helper_index": len(index),
        "helper_limit_per_state": helper_limit_per_state,
        "elapsed_seconds": time.perf_counter() - started,
        "expanded": expanded,
        "generated": generated,
        "seen": len(seen_depth),
        "helper_selection_total": helper_selection_total,
        "symmetry_prunes": symmetry_prunes,
        "no_op_prunes": no_op_prunes,
        "depth_histogram": depth_histogram,
        "stop_reason": stop_reason,
        "hit": None if hit is None else {"code": hit.code, "depth": hit.depth, "path": hit.path},
        "closest": closest,
    }


if __name__ == "__main__":
    print(json.dumps(search_macro_v2(), ensure_ascii=False, indent=2))
