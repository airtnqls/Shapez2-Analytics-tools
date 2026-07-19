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

from legacy_corner_recipe import Shape, rotate, structural  # noqa: E402

BLOCK = ("SS--", "-S--", "SS--", "-S--", "cS--")
PREFIX = ("SS--",)


def family_code(repeats: int) -> str:
    return ":".join(PREFIX + BLOCK * repeats)


def from_struct(code: str, cap: int) -> Shape:
    shape = Shape.from_string(code)
    shape.max_layers = cap
    return shape


def stable(shape: Shape, cap: int) -> Shape:
    shape.max_layers = cap
    result = shape.apply_physics()
    result.max_layers = cap
    return result


def unique_rotations(shape: Shape):
    result = []
    seen = set()
    for turns in range(4):
        candidate = rotate(shape, turns)
        code = structural(candidate)
        if code not in seen:
            seen.add(code)
            result.append((turns, candidate))
    return result


def rows(code: str, cap: int) -> list[str]:
    out = code.split(":") if code else []
    return (out + ["----"] * cap)[:cap]


def distance(code: str, goal: str, cap: int) -> dict[str, int]:
    mismatch = unwanted_p = missing_c = unwanted_c = missing_s = extra = 0
    for a, b in zip(rows(code, cap), rows(goal, cap)):
        for x, y in zip(a, b):
            if x == y:
                continue
            mismatch += 1
            unwanted_p += x == "P"
            missing_c += y == "c" and x != "c"
            unwanted_c += x == "c" and y != "c"
            missing_s += y == "S" and x != "S"
            extra += y == "-" and x != "-"
    return {
        "mismatch": int(mismatch),
        "unwanted_p": int(unwanted_p),
        "missing_c": int(missing_c),
        "unwanted_c": int(unwanted_c),
        "missing_s": int(missing_s),
        "extra": int(extra),
    }


def score(code: str, goal: str, cap: int, depth: int) -> tuple[int, int, int, int, int]:
    d = distance(code, goal, cap)
    return (
        15 * d["mismatch"] + 18 * d["missing_c"] + 8 * d["unwanted_c"] + 4 * d["unwanted_p"] + depth,
        d["mismatch"],
        d["missing_c"],
        d["unwanted_p"],
        len(code),
    )


@dataclass(frozen=True)
class Helper:
    name: str
    code: str
    proof: tuple[dict, ...]
    depth: int


@dataclass
class Node:
    code: str
    path: list[dict]
    depth: int


def add_helper(pool: dict[str, Helper], name: str, shape: Shape, proof: list[dict], depth: int, cap: int) -> bool:
    result = stable(shape, cap)
    code = structural(result)
    if not code or code in pool:
        return False
    pool[code] = Helper(name, code, tuple(proof), depth)
    return True


def build_helper_pool(cap: int, max_depth: int = 2, max_helpers: int = 1200) -> list[Helper]:
    pool: dict[str, Helper] = {}
    frontier: list[Helper] = []

    for mask in range(1, 16):
        row = "".join("S" if mask & (1 << q) else "-" for q in range(4))
        shape = from_struct(row, cap)
        if add_helper(pool, f"RAW_{mask:02x}", shape, [{"op": "RAW_INPUT", "mask": mask}], 0, cap):
            frontier.append(pool[structural(stable(shape, cap))])

    for depth in range(1, max_depth + 1):
        new_frontier: list[Helper] = []
        current_all = list(pool.values())
        primary = frontier

        for helper in primary:
            shape = from_struct(helper.code, cap)
            unary = []
            for turns, rotated in unique_rotations(shape):
                if turns:
                    unary.append((f"{helper.name}_R{turns}", rotated, list(helper.proof) + [{"op": "ROTATE", "turns": turns}]))
                unary.append((f"{helper.name}_PIN", rotated.push_pin(), list(helper.proof) + [{"op": "PIN_PUSH", "pre_turns": turns}]))
                unary.append((f"{helper.name}_GEN", rotated.crystal_generator("y"), list(helper.proof) + [{"op": "CRYSTAL_GENERATOR", "pre_turns": turns}]))
                for kind, outputs in (
                    ("SC", rotated.simple_cutter()),
                    ("HC", rotated.half_cutter()),
                    ("QC", rotated.quad_cutter()),
                ):
                    for index, output in enumerate(outputs):
                        unary.append((f"{helper.name}_{kind}{index}", output, list(helper.proof) + [{"op": kind, "pre_turns": turns, "output": index}]))
            for name, output, proof in unary:
                if len(pool) >= max_helpers:
                    break
                if add_helper(pool, name, output, proof, depth, cap):
                    new_frontier.append(pool[structural(stable(output, cap))])

        # all × frontier, with symmetric Swap pairs interned.
        pair_seen = set()
        for left in current_all:
            if len(pool) >= max_helpers:
                break
            a = from_struct(left.code, cap)
            for right in primary:
                b = from_struct(right.code, cap)
                swap_key = tuple(sorted((left.code, right.code)))
                if swap_key not in pair_seen:
                    pair_seen.add(swap_key)
                    for index, output in enumerate(Shape.swap(a, b)):
                        name = f"SWAP_{left.name}_{right.name}_{index}"
                        proof = list(left.proof) + list(right.proof) + [{"op": "SWAP", "output": index}]
                        if add_helper(pool, name, output, proof, depth, cap):
                            new_frontier.append(pool[structural(stable(output, cap))])
                        if len(pool) >= max_helpers:
                            break
                if len(pool) >= max_helpers:
                    break
                for order, output in (
                    ("LR", Shape.stack(a, b)),
                    ("RL", Shape.stack(b, a)),
                ):
                    name = f"STACK_{order}_{left.name}_{right.name}"
                    proof = list(left.proof) + list(right.proof) + [{"op": "STACK", "order": order}]
                    if add_helper(pool, name, output, proof, depth, cap):
                        new_frontier.append(pool[structural(stable(output, cap))])
                    if len(pool) >= max_helpers:
                        break

        frontier = new_frontier
        if not frontier or len(pool) >= max_helpers:
            break

    return sorted(pool.values(), key=lambda h: (h.depth, len(h.proof), h.code, h.name))


def current_unary(node: Node, cap: int) -> list[Node]:
    shape = from_struct(node.code, cap)
    out = []
    seen = set()
    for turns, rotated in unique_rotations(shape):
        candidates = [
            ("PIN_PUSH", rotated.push_pin(), {"op": "PIN_PUSH", "pre_turns": turns}),
            ("CRYSTAL_GENERATOR", rotated.crystal_generator("y"), {"op": "CRYSTAL_GENERATOR", "pre_turns": turns}),
        ]
        for kind, outputs in (
            ("SIMPLE_CUT", rotated.simple_cutter()),
            ("HALF_CUT", rotated.half_cutter()),
            ("QUAD_CUT", rotated.quad_cutter()),
        ):
            for index, output in enumerate(outputs):
                candidates.append((kind, output, {"op": kind, "pre_turns": turns, "output": index}))
        for name, candidate, step in candidates:
            code = structural(stable(candidate, cap))
            if code and code != node.code and code not in seen:
                seen.add(code)
                out.append(Node(code, node.path + [step], node.depth + 1))
    return out


def current_binary(node: Node, helpers: list[Helper], cap: int) -> list[Node]:
    current = from_struct(node.code, cap)
    out = []
    seen = set()
    for current_turns, a in unique_rotations(current):
        for helper in helpers:
            b0 = from_struct(helper.code, cap)
            for helper_turns, b in unique_rotations(b0):
                for index, output in enumerate(Shape.swap(a, b)):
                    for final_turns, candidate in unique_rotations(output):
                        code = structural(stable(candidate, cap))
                        if code and code not in seen and code != node.code:
                            seen.add(code)
                            out.append(Node(code, node.path + [{
                                "op": "SWAP",
                                "current_turns": current_turns,
                                "helper": helper.name,
                                "helper_code": helper.code,
                                "helper_proof": list(helper.proof),
                                "helper_turns": helper_turns,
                                "output": index,
                                "final_turns": final_turns,
                            }], node.depth + 1))
                for order, output in (
                    ("CURRENT_BOTTOM", Shape.stack(a, b)),
                    ("HELPER_BOTTOM", Shape.stack(b, a)),
                ):
                    for final_turns, candidate in unique_rotations(output):
                        code = structural(stable(candidate, cap))
                        if code and code not in seen and code != node.code:
                            seen.add(code)
                            out.append(Node(code, node.path + [{
                                "op": "STACK",
                                "order": order,
                                "current_turns": current_turns,
                                "helper": helper.name,
                                "helper_code": helper.code,
                                "helper_proof": list(helper.proof),
                                "helper_turns": helper_turns,
                                "final_turns": final_turns,
                            }], node.depth + 1))
    return out


def search_macro(
    repeats: int = 1,
    *,
    max_depth: int = 6,
    beam_width: int = 96,
    helper_limit: int = 160,
    max_seconds: float = 100.0,
    state_limit: int = 30000,
) -> dict:
    started = time.perf_counter()
    cap = 1 + 5 * (repeats + 1)
    Shape.MAX_LAYERS = cap
    start_code = structural(stable(from_struct(family_code(repeats), cap), cap))
    goal_code = structural(stable(from_struct(family_code(repeats + 1), cap), cap))
    all_helpers = build_helper_pool(cap, max_depth=2, max_helpers=1200)
    all_helpers.sort(key=lambda h: (score(h.code, goal_code, cap, h.depth), h.depth, len(h.proof), h.name))
    helpers = all_helpers[:helper_limit]

    start = Node(start_code, [], 0)
    queue = [(score(start.code, goal_code, cap, 0), 0, start)]
    serial = 1
    seen_depth = {start.code: 0}
    expanded = generated = 0
    hit = None
    closest_nodes: dict[str, Node] = {start.code: start}
    depth_histogram: dict[int, int] = {}
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

        candidates = {}
        for node in batch:
            expanded += 1
            depth_histogram[node.depth] = depth_histogram.get(node.depth, 0) + 1
            closest_nodes.setdefault(node.code, node)
            if node.code == goal_code:
                hit = node
                stop_reason = "hit"
                break
            if node.depth >= max_depth:
                continue

            successors = current_unary(node, cap)
            d = distance(node.code, goal_code, cap)
            if node.depth <= 2 or d["mismatch"] <= 16:
                successors.extend(current_binary(node, helpers, cap))
            generated += len(successors)
            for child in successors:
                old_depth = seen_depth.get(child.code)
                if old_depth is not None and old_depth <= child.depth:
                    continue
                seen_depth[child.code] = child.depth
                old = candidates.get(child.code)
                if old is None or score(child.code, goal_code, cap, child.depth) < score(old.code, goal_code, cap, old.depth):
                    candidates[child.code] = child
            if time.perf_counter() - started >= max_seconds:
                stop_reason = "time-limit"
                break
        if hit is not None or stop_reason == "time-limit":
            break

        ranked = sorted(candidates.values(), key=lambda n: (score(n.code, goal_code, cap, n.depth), len(n.path), n.code))
        for child in ranked[: beam_width * 4]:
            heapq.heappush(queue, (score(child.code, goal_code, cap, child.depth), serial, child))
            serial += 1

    candidates = list(closest_nodes.values()) + [node for _p, _s, node in queue[: beam_width * 4]]
    unique = {}
    for node in sorted(candidates, key=lambda n: (score(n.code, goal_code, cap, n.depth), len(n.path), n.code)):
        unique.setdefault(node.code, node)
    closest = []
    for node in list(unique.values())[:12]:
        closest.append({
            "score": score(node.code, goal_code, cap, node.depth),
            "distance": distance(node.code, goal_code, cap),
            "code": node.code,
            "depth": node.depth,
            "path": node.path,
        })

    return {
        "schema_version": 1,
        "family": "F_n = SS-- + (SS--,-S--,SS--,-S--,cS--)^n",
        "repeats": repeats,
        "cap": cap,
        "start": start_code,
        "goal": goal_code,
        "helper_pool_total": len(all_helpers),
        "helpers_used": len(helpers),
        "parameters": {
            "max_depth": max_depth,
            "beam_width": beam_width,
            "helper_limit": helper_limit,
            "max_seconds": max_seconds,
            "state_limit": state_limit,
        },
        "elapsed_seconds": time.perf_counter() - started,
        "expanded": expanded,
        "generated": generated,
        "seen": len(seen_depth),
        "depth_histogram": depth_histogram,
        "stop_reason": stop_reason,
        "hit": None if hit is None else {"code": hit.code, "depth": hit.depth, "path": hit.path},
        "closest": closest,
    }


if __name__ == "__main__":
    print(json.dumps(search_macro(), ensure_ascii=False, indent=2))
