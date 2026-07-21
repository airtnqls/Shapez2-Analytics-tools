from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import is_craftable_column
from backend.corner_half.global_predecessor import compile_global_predecessor
from backend.corner_half.structural_ops import cut, rotate, stack, swap
from backend.corner_half.structural_physics import EMPTY, code, column, is_stable, parse

TARGET_COLUMN = "SS-S-cS-S-c"
CAP = len(TARGET_COLUMN)


def rows_from_columns(values: tuple[str, str, str, str]):
    return [
        [values[q][layer] if layer < len(values[q]) else EMPTY for q in range(4)]
        for layer in range(CAP)
    ]


def fixed_rows(rows):
    out = [list(row) for row in rows[:CAP]]
    while len(out) < CAP:
        out.append([EMPTY] * 4)
    return out


def state_candidates():
    first = compile_global_predecessor(TARGET_COLUMN, CAP)
    pushed = parse(first.pushed, CAP)
    stacked = stack(pushed, parse("---S:---S", CAP), CAP)
    tower = "S" * CAP
    helpers = [
        ("east:T,-", rows_from_columns((tower, "", "", ""))),
        ("east:-,T", rows_from_columns(("", tower, "", ""))),
        ("east:T,T", rows_from_columns((tower, tower, "", ""))),
        ("west:T,-", rows_from_columns(("", "", tower, ""))),
        ("west:-,T", rows_from_columns(("", "", "", tower))),
        ("west:T,T", rows_from_columns(("", "", tower, tower))),
    ]
    seen = {}
    for helper_name, helper in helpers:
        for order_name, left, right in (
            ("current-helper", stacked, helper),
            ("helper-current", helper, stacked),
        ):
            for output_index, output in enumerate(swap(left, right, CAP)):
                for turns in range(4):
                    state = fixed_rows(rotate(output, turns))
                    state_code = code(state)
                    seen.setdefault(state_code, {
                        "state": state,
                        "source": f"{helper_name}/{order_name}/out{output_index}/rot{turns}",
                    })
    return first, list(seen.values())


def half_distance(a, b) -> int:
    aa = fixed_rows(a)
    bb = fixed_rows(b)
    return sum(aa[l][q] != bb[l][q] for l in range(CAP) for q in range(4))


def craftable_half(rows) -> bool:
    values = [column(rows, q) for q in range(4)]
    occupied = [q for q, value in enumerate(values) if value]
    if not is_stable(rows):
        return False
    return all(is_craftable_column(values[q]) for q in occupied)


def factor(report_path: Path) -> dict[str, object]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    predecessor_code = data.get("result", {}).get("predecessor")
    if not predecessor_code:
        return {
            "schemaVersion": 1,
            "predecessorFound": False,
            "input": data,
            "matches": [],
        }
    predecessor = fixed_rows(parse(predecessor_code, CAP))
    pred_east, pred_west = cut(predecessor, CAP)
    pred_east = fixed_rows(pred_east)
    pred_west = fixed_rows(pred_west)

    first, states = state_candidates()
    matches = []
    nearest = []
    for item in states:
        state = item["state"]
        state_east, state_west = cut(state, CAP)
        state_east = fixed_rows(state_east)
        state_west = fixed_rows(state_west)

        # Preserve the state's east half and import the predecessor west half.
        helper_west = fixed_rows(pred_west)
        helper = helper_west
        helper_code = code(helper)
        if craftable_half(helper):
            for order_name, left, right in (("state-helper", state, helper), ("helper-state", helper, state)):
                for output_index, output in enumerate(swap(left, right, CAP)):
                    if code(output) == predecessor_code:
                        matches.append({
                            "stateSource": item["source"],
                            "state": code(state),
                            "preserved": "east",
                            "helper": helper_code,
                            "helperPillars": [column(helper, q) for q in range(4)],
                            "swapOrder": order_name,
                            "swapOutput": output_index,
                        })

        # Preserve the state's west half and import the predecessor east half.
        helper_east = fixed_rows(pred_east)
        helper = helper_east
        helper_code = code(helper)
        if craftable_half(helper):
            for order_name, left, right in (("state-helper", state, helper), ("helper-state", helper, state)):
                for output_index, output in enumerate(swap(left, right, CAP)):
                    if code(output) == predecessor_code:
                        matches.append({
                            "stateSource": item["source"],
                            "state": code(state),
                            "preserved": "west",
                            "helper": helper_code,
                            "helperPillars": [column(helper, q) for q in range(4)],
                            "swapOrder": order_name,
                            "swapOutput": output_index,
                        })

        nearest.append({
            "stateSource": item["source"],
            "state": code(state),
            "eastDistance": half_distance(state_east, pred_east),
            "westDistance": half_distance(state_west, pred_west),
            "statePillars": [column(state, q) for q in range(4)],
        })

    nearest.sort(key=lambda item: (min(item["eastDistance"], item["westDistance"]), item["eastDistance"] + item["westDistance"], item["stateSource"]))
    return {
        "schemaVersion": 1,
        "predecessorFound": True,
        "predecessor": predecessor_code,
        "predecessorPillars": [column(predecessor, q) for q in range(4)],
        "predecessorStable": is_stable(predecessor),
        "predecessorColumnsCraftable": [is_craftable_column(column(predecessor, q)) for q in range(4)],
        "firstPredecessor": first.predecessor,
        "firstStateCount": len(states),
        "matches": matches,
        "nearest": nearest[:20],
    }


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "reports/half-any-predecessor-probe.json"
    output = factor(input_path)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
