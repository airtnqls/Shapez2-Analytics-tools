from __future__ import annotations

import contextlib
import io
import json
import sys
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


def from_struct(code: str) -> Shape:
    shape = Shape.from_string(code)
    shape.max_layers = len(TARGET_LEFT_PILLAR)
    return shape


def rows(code: str) -> list[str]:
    return code.split(":") if code else []


def replace_symbols(code: str, mapping: dict[str, str]) -> str:
    return ":".join("".join(mapping.get(ch, ch) for ch in row) for row in rows(code))


def normalized(shape: Shape) -> Shape:
    out = shape.apply_physics()
    out.max_layers = len(TARGET_LEFT_PILLAR)
    return out


def distance(a: str, b: str) -> int:
    ar = rows(a)
    br = rows(b)
    n = max(len(ar), len(br))
    total = 0
    for i in range(n):
        x = ar[i] if i < len(ar) else "----"
        y = br[i] if i < len(br) else "----"
        total += sum(cx != cy for cx, cy in zip(x, y))
    return total


def make_auxiliaries(pin_result: Shape, target: Shape) -> list[tuple[str, Shape]]:
    cap = len(TARGET_LEFT_PILLAR)
    candidates: list[tuple[str, Shape]] = []

    def add(name: str, shape: Shape) -> None:
        shape.max_layers = cap
        stable = normalized(shape)
        key = structural(stable)
        if key not in seen:
            seen.add(key)
            candidates.append((name, stable))

    seen: set[str] = set()
    add("EMPTY", Shape([]))

    for mask in range(1, 16):
        row = "".join("S" if mask & (1 << q) else "-" for q in range(4))
        add(f"SOLID_MASK_{mask:02x}", from_struct(":".join(row for _ in range(cap))))

    target_s = replace_symbols(structural(target), {"c": "S", "P": "S"})
    add("TARGET_ALL_S", from_struct(target_s))
    target_no_c = replace_symbols(structural(target), {"c": "-", "P": "-"})
    add("TARGET_NO_EVENTS", from_struct(target_no_c))

    pin_code = structural(pin_result)
    for name, mapping in (
        ("PIN_ALL_S", {"c": "S", "P": "S"}),
        ("PIN_DROP_C", {"c": "-", "P": "S"}),
        ("PIN_DROP_P", {"c": "S", "P": "-"}),
        ("PIN_ONLY_S", {"c": "-", "P": "-"}),
    ):
        add(name, from_struct(replace_symbols(pin_code, mapping)))

    # Target-derived individual columns and adjacent halves with events replaced
    # by ordinary S, so they remain cheap/simple auxiliary inputs.
    target_rows = rows(structural(target))
    for mask in (1, 2, 4, 8, 3, 6, 12, 9):
        out_rows = []
        for row in target_rows:
            out_rows.append("".join(("S" if row[q] != "-" else "-") if mask & (1 << q) else "-" for q in range(4)))
        add(f"TARGET_MASK_{mask:02x}", from_struct(":".join(out_rows)))

    return candidates


@dataclass
class SearchNode:
    code: str
    path: list[dict]


def expand_cutters(shape: Shape, path: list[dict]) -> list[SearchNode]:
    out: list[SearchNode] = []
    for turns in range(4):
        rotated = rotate(shape, turns)
        for kind, pieces in (
            ("simple_cut", rotated.simple_cutter()),
            ("half_cut", rotated.half_cutter()),
            ("quad_cut", rotated.quad_cutter()),
        ):
            for index, piece in enumerate(pieces):
                for final_turns in range(4):
                    candidate = rotate(piece, final_turns)
                    out.append(SearchNode(structural(candidate), path + [{"op": kind, "pre_turns": turns, "output": index, "post_turns": final_turns}]))
    return out


def search(max_swap_depth: int = 2, state_limit: int = 12000) -> dict:
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap

    with contextlib.redirect_stdout(io.StringIO()):
        predecessor = from_struct(build_pinable_shape(TARGET_LEFT_PILLAR))
    pin_result = predecessor.push_pin()
    target = from_struct(TARGET_CODE)
    goal = structural(target)
    auxiliaries = make_auxiliaries(pin_result, target)

    start = SearchNode(structural(pin_result), [{"op": "PIN_PUSH", "input": structural(predecessor)}])
    frontier = [start]
    seen = {start.code}
    best: list[tuple[int, str, list[dict]]] = [(distance(start.code, goal), start.code, start.path)]
    hits: list[dict] = []
    depth_counts = [1]

    # Cut-only possibilities from the initial result.
    for node in expand_cutters(pin_result, start.path):
        d = distance(node.code, goal)
        best.append((d, node.code, node.path))
        if node.code == goal:
            hits.append({"code": node.code, "path": node.path})

    for depth in range(1, max_swap_depth + 1):
        next_frontier: list[SearchNode] = []
        for node in frontier:
            current = from_struct(node.code)
            for current_turns in range(4):
                a = rotate(current, current_turns)
                for aux_name, aux in auxiliaries:
                    for aux_turns in range(4):
                        b = rotate(aux, aux_turns)
                        out_a, out_b = Shape.swap(a, b)
                        for output_index, output in enumerate((out_a, out_b)):
                            for final_turns in range(4):
                                candidate = rotate(output, final_turns)
                                code = structural(candidate)
                                path = node.path + [{
                                    "op": "SWAP",
                                    "current_turns": current_turns,
                                    "aux": aux_name,
                                    "aux_turns": aux_turns,
                                    "output": output_index,
                                    "final_turns": final_turns,
                                }]
                                d = distance(code, goal)
                                best.append((d, code, path))
                                if code == goal:
                                    hits.append({"code": code, "path": path})
                                    return {
                                        "schema_version": 1,
                                        "goal": goal,
                                        "pin_result": structural(pin_result),
                                        "auxiliary_count": len(auxiliaries),
                                        "depth_counts": depth_counts + [len(next_frontier)],
                                        "hit": hits[0],
                                        "closest": [],
                                    }
                                if code not in seen and len(seen) < state_limit:
                                    seen.add(code)
                                    next_frontier.append(SearchNode(code, path))
        frontier = next_frontier
        depth_counts.append(len(frontier))
        if not frontier or len(seen) >= state_limit:
            break

    unique_best: dict[str, tuple[int, str, list[dict]]] = {}
    for item in sorted(best, key=lambda x: (x[0], len(x[2]), x[1])):
        unique_best.setdefault(item[1], item)
    closest = [
        {"distance": d, "code": code, "path": path}
        for d, code, path in list(unique_best.values())[:12]
    ]
    return {
        "schema_version": 1,
        "goal": goal,
        "pin_result": structural(pin_result),
        "auxiliary_count": len(auxiliaries),
        "states_seen": len(seen),
        "depth_counts": depth_counts,
        "hit": hits[0] if hits else None,
        "closest": closest,
    }


if __name__ == "__main__":
    print(json.dumps(search(), ensure_ascii=False, indent=2))
