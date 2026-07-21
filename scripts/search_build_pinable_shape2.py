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
    """Finish the legacy function's omitted pre-Pin one-row shift."""
    snapshot = packed_snapshot(target)
    return (snapshot[1:] + EMPTY).rstrip(EMPTY)


def fixed_rows(rows, cap: int):
    out = [list(row) for row in rows[:cap]]
    while len(out) < cap:
        out.append([EMPTY] * 4)
    return out


def first_swap_states(first, cap: int):
    """Exact states after Pin, the small Stack, and the first tower Swapper."""
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
        for stack_order, bottom, top in (("current-bottom", pushed, stack_helper), ("helper-bottom", stack_helper, pushed)):
            stacked = stack(bottom, top, cap)
            for helper_name, helper in tower_helpers:
                for swap_order, left, right in (("current-helper", stacked, helper), ("helper-current", helper, stacked)):
                    for output_index, output in enumerate(swap(left, right, cap)):
                        for turns in range(4):
                            state = fixed_rows(rotate(output, turns), cap)
                            states.setdefault(code(state), {
                                "state": state,
                                "source": f"{stack_name}/{stack_order}/{helper_name}/{swap_order}/out{output_index}/rot{turns}",
                                "pillars": [column(state, q) for q in range(4)],
                            })
    return list(states.values())


def factor_through_second_swap(pre_final, states, cap: int) -> list[dict[str, object]]:
    """Replay every constant first-state/second-Swap orientation exactly."""
    target_code = code(pre_final)
    pre_east, pre_west = cut(pre_final, cap)
    factors: list[dict[str, object]] = []
    for item in states:
        state = item["state"]
        for preserved, helper in (("east", pre_west), ("west", pre_east)):
            helper = fixed_rows(helper, cap)
            occupied = [column(helper, q) for q in range(4) if column(helper, q)]
            if not is_stable(helper) or not all(is_craftable_column(value) for value in occupied):
                continue
            for order, left, right in (("state-helper", state, helper), ("helper-state", helper, state)):
                for output_index, output in enumerate(swap(left, right, cap)):
                    for turns in range(4):
                        if code(rotate(output, turns)) == target_code:
                            factors.append({
                                "stateSource": item["source"],
                                "state": code(state),
                                "statePillars": item["pillars"],
                                "preserved": preserved,
                                "helper": code(helper),
                                "helperPillars": [column(helper, q) for q in range(4)],
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
    shifted = pre_pin_compacted_a(target)
    states = first_swap_states(first, cap)

    # Ordered by how literally each layout follows the unfinished legacy
    # build_pinable_shape2 sketch and the supplied screenshot.  This keeps the
    # exhaustive search below a few million width-four replays.
    layouts = []
    for a_kind, a in (
        ("shifted-packed", shifted),
        ("unshifted-packed", snapshot),
        ("plain-shift", target[1:].rstrip(EMPTY)),
    ):
        for helper_order in ("a-b", "b-a"):
            first_col, second_col = (a, "{B}") if helper_order == "a-b" else ("{B}", a)
            for fixed_name, x, y in (
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
            ):
                layouts.append((a_kind, helper_order, first_col, second_col, fixed_name, x, y))

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
        for a_kind, helper_order, first_token, second_token, fixed_name, x, y in layouts:
            first_col = b if first_token == "{B}" else first_token
            second_col = b if second_token == "{B}" else second_token
            helper = rows_from_columns((first_col, second_col, "", ""), cap)
            if not is_stable(helper):
                continue
            helper_stable += 1
            full = rows_from_columns((first_col, second_col, x, y), cap)
            if not is_stable(full):
                continue
            full_stable += 1
            out = push_pin(full, cap)
            replayed += 1
            if column(out, 0) != target:
                continue
            factors = factor_through_second_swap(full, states, cap)
            hits.append({
                "aKind": a_kind,
                "a": first_col if helper_order == "a-b" else second_col,
                "b": b,
                "helperOrder": helper_order,
                "fixedPair": fixed_name,
                "preFinal": code(full),
                "preFinalPillars": [column(full, q) for q in range(4)],
                "afterFinalPin": code(out),
                "afterFinalPillars": [column(out, q) for q in range(4)],
                "secondSwapFactors": factors[:20],
            })
            if len(hits) >= max_hits:
                break
        if len(hits) >= max_hits:
            break

    return {
        "target": target,
        "cap": cap,
        "firstPredecessor": first.predecessor,
        "afterFirstPin": first.pushed,
        "a1": a1,
        "b1": b1,
        "snapshot": snapshot,
        "a2Shifted": shifted,
        "alphabet": alphabet,
        "firstStates": len(states),
        "layouts": len(layouts),
        "checked": checked,
        "craftable": craftable,
        "helperStable": helper_stable,
        "fullStable": full_stable,
        "replayed": replayed,
        "hits": hits,
    }


def main() -> None:
    reports = []
    for target in ("SS-S-cS-S-c",):
        try:
            reports.append(search(target))
        except BaseException as exc:
            reports.append({
                "target": target,
                "errorType": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })
    print(json.dumps({"schemaVersion": 4, "reports": reports}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
