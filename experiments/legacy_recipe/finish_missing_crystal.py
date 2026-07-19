from __future__ import annotations

import heapq
import json
import time
from dataclasses import dataclass

from search_family_macro import (
    Helper,
    Node,
    build_helper_pool,
    from_struct,
    stable,
    structural,
    unique_rotations,
    Shape,
)
from search_family_macro_v2 import helper_index, mismatch_profile, select_helpers

START = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:-S--"
GOAL = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = 11


def padded_rows(code: str) -> list[str]:
    parts = code.split(":") if code else []
    return (parts + ["----"] * CAP)[:CAP]


def metrics(code: str) -> dict[str, int]:
    mismatch = missing_c = unwanted_c = unwanted_p = missing_s = extra = 0
    for a, b in zip(padded_rows(code), padded_rows(GOAL)):
        for x, y in zip(a, b):
            if x == y:
                continue
            mismatch += 1
            missing_c += y == "c" and x != "c"
            unwanted_c += x == "c" and y != "c"
            unwanted_p += x == "P"
            missing_s += y == "S" and x != "S"
            extra += y == "-" and x != "-"
    return {
        "mismatch": int(mismatch),
        "missing_c": int(missing_c),
        "unwanted_c": int(unwanted_c),
        "unwanted_p": int(unwanted_p),
        "missing_s": int(missing_s),
        "extra": int(extra),
    }


def score(code: str, depth: int, phase: str) -> tuple[int, int, int, int, int]:
    m = metrics(code)
    phase_penalty = 0 if phase == "after-generator" else 2
    return (
        20 * m["mismatch"] + 30 * m["missing_c"] + 10 * m["unwanted_c"] + 4 * m["unwanted_p"] + depth + phase_penalty,
        m["mismatch"],
        m["missing_c"],
        m["unwanted_c"],
        len(code),
    )


@dataclass
class PhaseNode:
    code: str
    phase: str
    depth: int
    path: list[dict]


def unique_add(store: dict[tuple[str, str], PhaseNode], node: PhaseNode) -> None:
    key = (node.code, node.phase)
    old = store.get(key)
    if old is None or (node.depth, len(node.path)) < (old.depth, len(old.path)):
        store[key] = node


def unary_cleanup(node: PhaseNode) -> list[PhaseNode]:
    shape = from_struct(node.code, CAP)
    result = []
    seen = set()
    for turns, rotated in unique_rotations(shape):
        candidates = []
        if node.phase == "before-generator":
            generated = rotated.crystal_generator("y")
            candidates.append(("CRYSTAL_GENERATOR", generated, "after-generator", {"op": "CRYSTAL_GENERATOR", "pre_turns": turns}))
        if node.phase == "after-generator":
            candidates.append(("PIN_PUSH", rotated.push_pin(), node.phase, {"op": "PIN_PUSH", "pre_turns": turns}))
        for kind, outputs in (
            ("SIMPLE_CUT", rotated.simple_cutter()),
            ("HALF_CUT", rotated.half_cutter()),
            ("QUAD_CUT", rotated.quad_cutter()),
        ):
            for index, output in enumerate(outputs):
                candidates.append((kind, output, node.phase, {"op": kind, "pre_turns": turns, "output": index}))
        for _name, output, phase, step in candidates:
            code = structural(stable(output, CAP))
            key = (code, phase)
            if code and code != node.code and key not in seen:
                seen.add(key)
                result.append(PhaseNode(code, phase, node.depth + 1, node.path + [step]))
    return result


def binary_successors(node: PhaseNode, selected, limit: int = 128) -> tuple[list[PhaseNode], dict[str, int]]:
    shape = from_struct(node.code, CAP)
    candidates: dict[tuple[str, str], PhaseNode] = {}
    seen_outputs = set()
    generated = symmetry = noop = 0

    for current_turns, current in unique_rotations(shape):
        for helper in selected:
            other = helper.shape
            for index, output in enumerate(Shape.swap(current, other)):
                generated += 1
                for final_turns, candidate in unique_rotations(output):
                    code = structural(stable(candidate, CAP))
                    key = (code, node.phase)
                    if not code or code == node.code:
                        noop += 1
                        continue
                    if key in seen_outputs:
                        symmetry += 1
                        continue
                    seen_outputs.add(key)
                    unique_add(candidates, PhaseNode(code, node.phase, node.depth + 1, node.path + [{
                        "op": "SWAP",
                        "current_turns": current_turns,
                        "helper": helper.helper.name,
                        "helper_code": helper.helper.code,
                        "helper_proof": list(helper.helper.proof),
                        "helper_turns": helper.turns,
                        "output": index,
                        "final_turns": final_turns,
                    }]))
            for order, output in (
                ("CURRENT_BOTTOM", Shape.stack(current, other)),
                ("HELPER_BOTTOM", Shape.stack(other, current)),
            ):
                generated += 1
                for final_turns, candidate in unique_rotations(output):
                    code = structural(stable(candidate, CAP))
                    key = (code, node.phase)
                    if not code or code == node.code:
                        noop += 1
                        continue
                    if key in seen_outputs:
                        symmetry += 1
                        continue
                    seen_outputs.add(key)
                    unique_add(candidates, PhaseNode(code, node.phase, node.depth + 1, node.path + [{
                        "op": "STACK",
                        "order": order,
                        "current_turns": current_turns,
                        "helper": helper.helper.name,
                        "helper_code": helper.helper.code,
                        "helper_proof": list(helper.helper.proof),
                        "helper_turns": helper.turns,
                        "final_turns": final_turns,
                    }]))

    ranked = sorted(candidates.values(), key=lambda n: (score(n.code, n.depth, n.phase), len(n.path), n.code))[:limit]
    return ranked, {"generated": generated, "symmetry": symmetry, "noop": noop}


def search(
    *,
    max_depth: int = 5,
    beam_width: int = 128,
    helper_limit: int = 18,
    max_seconds: float = 110.0,
    state_limit: int = 50000,
) -> dict:
    started = time.perf_counter()
    Shape.MAX_LAYERS = CAP
    helper_pool = build_helper_pool(CAP, max_depth=2, max_helpers=1800)
    index = helper_index(helper_pool, CAP)

    start = PhaseNode(START, "before-generator", 0, [])
    queue = [(score(start.code, 0, start.phase), 0, start)]
    serial = 1
    best_depth = {(start.code, start.phase): 0}
    expanded = generated = symmetry = noop = 0
    phase_expanded = {"before-generator": 0, "after-generator": 0}
    closest = {(start.code, start.phase): start}
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
            if best_depth.get((node.code, node.phase)) != node.depth:
                continue
            batch.append(node)
        if not batch:
            break

        next_nodes = {}
        for node in batch:
            expanded += 1
            phase_expanded[node.phase] += 1
            closest.setdefault((node.code, node.phase), node)
            if node.code == GOAL:
                hit = node
                stop_reason = "hit"
                break
            if node.depth >= max_depth:
                continue

            for child in unary_cleanup(node):
                generated += 1
                if child.code == GOAL:
                    hit = child
                    stop_reason = "hit"
                    break
                key = (child.code, child.phase)
                if best_depth.get(key, 10**9) <= child.depth:
                    continue
                best_depth[key] = child.depth
                unique_add(next_nodes, child)
            if hit is not None:
                break

            selected = select_helpers(index, node.code, GOAL, CAP, helper_limit)
            children, counts = binary_successors(node, selected, limit=beam_width)
            generated += counts["generated"]
            symmetry += counts["symmetry"]
            noop += counts["noop"]
            for child in children:
                if child.code == GOAL:
                    hit = child
                    stop_reason = "hit"
                    break
                key = (child.code, child.phase)
                if best_depth.get(key, 10**9) <= child.depth:
                    continue
                best_depth[key] = child.depth
                unique_add(next_nodes, child)
            if hit is not None:
                break

        if hit is not None:
            break
        ranked = sorted(next_nodes.values(), key=lambda n: (score(n.code, n.depth, n.phase), len(n.path), n.code))[: beam_width * 3]
        for child in ranked:
            heapq.heappush(queue, (score(child.code, child.depth, child.phase), serial, child))
            serial += 1

    all_nodes = list(closest.values()) + [node for _p, _s, node in queue[: beam_width * 3]]
    unique = {}
    for node in sorted(all_nodes, key=lambda n: (score(n.code, n.depth, n.phase), len(n.path), n.code)):
        unique.setdefault((node.code, node.phase), node)
    closest_rows = []
    for node in list(unique.values())[:10]:
        closest_rows.append({
            "score": score(node.code, node.depth, node.phase),
            "metrics": metrics(node.code),
            "code": node.code,
            "phase": node.phase,
            "depth": node.depth,
            "path": node.path,
        })

    return {
        "schema_version": 1,
        "problem": "insert the final missing top-left crystal into F2 without changing any other cell",
        "start": START,
        "goal": GOAL,
        "helper_pool": len(helper_pool),
        "rotated_helper_index": len(index),
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
        "symmetry_prunes": symmetry,
        "no_op_prunes": noop,
        "phase_expanded": phase_expanded,
        "stop_reason": stop_reason,
        "hit": None if hit is None else {"code": hit.code, "phase": hit.phase, "depth": hit.depth, "path": hit.path},
        "closest": closest_rows,
    }


if __name__ == "__main__":
    print(json.dumps(search(), ensure_ascii=False, indent=2))
