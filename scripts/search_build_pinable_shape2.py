from __future__ import annotations

import itertools
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import is_craftable_column
from backend.corner_half.global_predecessor import compile_global_predecessor
from backend.corner_half.structural_ops import cut, rotate, stack, swap
from backend.corner_half.structural_physics import EMPTY, code, column, is_stable, parse, push_pin


def rows_from_columns(values: tuple[str, str, str, str], cap: int):
    return [
        [values[q][layer] if layer < len(values[q]) else EMPTY for q in range(4)]
        for layer in range(cap)
    ]


def packed_snapshot(target: str) -> str:
    """Legacy build_pinable_shape2 prefix compaction before the lowest crystal."""
    low_c = target.find("c")
    if low_c < 0:
        raise ValueError("event target has no crystal")
    count_s = target[:low_c].count("S")
    a = list(target)
    placed = 0
    for layer in range(low_c - 1, -1, -1):
        if placed < count_s:
            a[layer] = "S"
            placed += 1
        else:
            a[layer] = EMPTY
    return "".join(a)


def pre_pin_compacted_a(target: str) -> str:
    """Convert the post-lift compact snapshot to its actual pre-Pin A column.

    The unfinished legacy function stopped before the same one-row left shift
    used by build_pinable_shape.  Pin Push inserts a receipt row and shifts the
    predecessor upward, so the pre-Pin column must drop snapshot row zero.
    """
    snapshot = packed_snapshot(target)
    return (snapshot[1:] + EMPTY).rstrip(EMPTY)


def fixed_rows(rows, cap: int):
    out = [list(row) for row in rows[:cap]]
    while len(out) < cap:
        out.append([EMPTY] * 4)
    return out


def target_column_hits(rows, target: str, cap: int) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for turns in range(4):
        oriented = rotate(rows, turns)
        for q in range(4):
            if column(oriented, q) == target:
                hits.append({"turns": turns, "column": q, "shape": code(oriented)})
    return hits


def first_swap_states(first, cap: int):
    """Exact states after the already-recovered Pin/Stack/first-Swap prefix."""
    pushed = parse(first.pushed, cap)
    tower = "S" * cap
    top_helpers = []
    for q in range(4):
        for height in (1, 2, 3):
            values = ["", "", "", ""]
            values[q] = "S" * height
            top_helpers.append((f"stack-q{q}-h{height}", rows_from_columns(tuple(values), cap)))

    tower_helpers = [
        ("east:T,-", rows_from_columns((tower, "", "", ""), cap)),
        ("east:-,T", rows_from_columns(("", tower, "", ""), cap)),
        ("east:T,T", rows_from_columns((tower, tower, "", ""), cap)),
        ("west:T,-", rows_from_columns(("", "", tower, ""), cap)),
        ("west:-,T", rows_from_columns(("", "", "", tower), cap)),
        ("west:T,T", rows_from_columns(("", "", tower, tower), cap)),
    ]

    states: dict[str, dict[str, object]] = {}
    for stack_name, stack_helper in top_helpers:
        for stack_order, bottom, top in (
            ("current-bottom", pushed, stack_helper),
            ("helper-bottom", stack_helper, pushed),
        ):
            stacked = stack(bottom, top, cap)
            for helper_name, helper in tower_helpers:
                for swap_order, left, right in (
                    ("current-helper", stacked, helper),
                    ("helper-current", helper, stacked),
                ):
                    for output_index, output in enumerate(swap(left, right, cap)):
                        for turns in range(4):
                            state = fixed_rows(rotate(output, turns), cap)
                            state_code = code(state)
                            states.setdefault(state_code, {
                                "state": state,
                                "source": f"{stack_name}/{stack_order}/{helper_name}/{swap_order}/out{output_index}/rot{turns}",
                                "pillars": [column(state, q) for q in range(4)],
                            })
    return list(states.values())


def factor_through_second_swap(pre_final, states, cap: int) -> list[dict[str, object]]:
    """Find an exact second-Swap factorization of a pre-final Pin predecessor."""
    target_code = code(pre_final)
    factors: list[dict[str, object]] = []
    for item in states:
        state = item["state"]
        state_east, state_west = cut(state, cap)
        for preserved, state_half, helper_half in (
            ("east", state_east, cut(pre_final, cap)[1]),
            ("west", state_west, cut(pre_final, cap)[0]),
        ):
            helper = fixed_rows(helper_half, cap)
            helper_columns = [column(helper, q) for q in range(4)]
            occupied = [value for value in helper_columns if value]
            if not is_stable(helper) or not all(is_craftable_column(value) for value in occupied):
                continue
            for order, left, right in (("state-helper", state, helper), ("helper-state", helper, state)):
                for output_index, output in enumerate(swap(left, right, cap)):
                    for turns in range(4):
                        oriented = rotate(output, turns)
                        if code(oriented) != target_code:
                            continue
                        factors.append({
                            "stateSource": item["source"],
                            "state": code(state),
                            "statePillars": item["pillars"],
                            "preserved": preserved,
                            "helper": code(helper),
                            "helperPillars": helper_columns,
                            "swapOrder": order,
                            "swapOutput": output_index,
                            "turns": turns,
                        })
    return factors


def search(target: str, *, alphabet: str = "-SP", max_hits: int = 30) -> dict:
    cap = len(target)
    first = compile_global_predecessor(target, cap)
    a1 = first.pushed_columns[0]
    b1 = first.pushed_columns[1]
    relay1 = first.pushed_columns[3]
    tower = "S" * cap
    snapshot = packed_snapshot(target)
    a2 = pre_pin_compacted_a(target)
    a_candidates = [
        ("shifted-packed", a2),
        ("unshifted-packed", snapshot),
        ("plain-shift", target[1:].rstrip(EMPTY)),
    ]
    fixed_pairs = [
        ("empty-a1", "", a1),
        ("a1-empty", a1, ""),
        ("a1-b1", a1, b1),
        ("b1-a1", b1, a1),
        ("empty-tower", "", tower),
        ("tower-empty", tower, ""),
        ("b1-tower", b1, tower),
        ("tower-b1", tower, b1),
        ("relay-tower", relay1, tower),
        ("tower-relay", tower, relay1),
    ]
    states = first_swap_states(first, cap)
    checked = craftable = helper_stable = full_stable = replayed = 0
    hits: list[dict[str, object]] = []

    seen: set[str] = set()
    for cells in itertools.product(alphabet, repeat=cap):
        b = "".join(cells).rstrip(EMPTY)
        if b in seen:
            continue
        seen.add(b)
        checked += 1
        if not is_craftable_column(b):
            continue
        craftable += 1
        for a_kind, a in a_candidates:
            for helper_order, first_col, second_col in (
                ("a-b", a, b),
                ("b-a", b, a),
            ):
                helper = rows_from_columns((first_col, second_col, "", ""), cap)
                if not is_stable(helper):
                    continue
                helper_stable += 1
                for fixed_name, x, y in fixed_pairs:
                    for side in ("helper-east", "helper-west"):
                        values = (first_col, second_col, x, y) if side == "helper-east" else (x, y, first_col, second_col)
                        base = rows_from_columns(values, cap)
                        for turns in range(4):
                            full = fixed_rows(rotate(base, turns), cap)
                            if not is_stable(full):
                                continue
                            full_stable += 1
                            out = push_pin(full, cap)
                            replayed += 1
                            column_hits = target_column_hits(out, target, cap)
                            if not column_hits:
                                continue
                            factors = factor_through_second_swap(full, states, cap)
                            hits.append({
                                "aKind": a_kind,
                                "a": a,
                                "b": b,
                                "helperOrder": helper_order,
                                "fixedPair": fixed_name,
                                "side": side,
                                "preTurns": turns,
                                "preFinal": code(full),
                                "preFinalPillars": [column(full, q) for q in range(4)],
                                "afterFinalPin": code(out),
                                "afterFinalPillars": [column(out, q) for q in range(4)],
                                "targetColumnHits": column_hits,
                                "secondSwapFactors": factors[:10],
                            })
                            if len(hits) >= max_hits:
                                return {
                                    "target": target,
                                    "cap": cap,
                                    "firstPredecessor": first.predecessor,
                                    "afterFirstPin": first.pushed,
                                    "a1": a1,
                                    "b1": b1,
                                    "snapshot": snapshot,
                                    "a2": a2,
                                    "alphabet": alphabet,
                                    "firstStates": len(states),
                                    "checked": checked,
                                    "craftable": craftable,
                                    "helperStable": helper_stable,
                                    "fullStable": full_stable,
                                    "replayed": replayed,
                                    "hits": hits,
                                }
    return {
        "target": target,
        "cap": cap,
        "firstPredecessor": first.predecessor,
        "afterFirstPin": first.pushed,
        "a1": a1,
        "b1": b1,
        "snapshot": snapshot,
        "a2": a2,
        "alphabet": alphabet,
        "firstStates": len(states),
        "checked": checked,
        "craftable": craftable,
        "helperStable": helper_stable,
        "fullStable": full_stable,
        "replayed": replayed,
        "hits": hits,
    }


def main() -> None:
    targets = ["SS-S-cS-S-c"]
    reports = []
    for target in targets:
        try:
            reports.append(search(target))
        except BaseException as exc:
            reports.append({
                "target": target,
                "errorType": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
    print(json.dumps({"schemaVersion": 3, "reports": reports}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
