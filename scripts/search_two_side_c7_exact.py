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
from backend.corner_half.corner_event_plan import compile_corner_event
from backend.corner_half.structural_physics import EMPTY, CRYSTAL, ORDINARY, PIN, code, column, is_stable, push_pin

TARGET = "SS-S-cS-S-c"
CAP = len(TARGET)


def set_cell(values: list[str], layer: int, value: str) -> bool:
    old = values[layer]
    if old == value:
        return True
    if old in (ORDINARY, EMPTY):
        values[layer] = value
        return True
    return False


def compile_two_side(
    post_a: str,
    mapping: tuple[tuple[int, int], ...],
    assignment: tuple[int, ...],
    *,
    filler: str,
    opposite_source: str,
):
    post_b = [filler] * (CAP + 1)
    post_d = [filler] * (CAP + 1)
    post_c = [CRYSTAL] * (CAP + 1)
    post_b[0] = post_d[0] = post_c[0] = PIN
    post_b[CAP] = post_d[CAP] = EMPTY
    sides = (post_b, post_d)
    moving = [(source, target) for source, target in mapping if source != target]
    conflict = None

    for index, (source, target) in enumerate(moving):
        side_index = assignment[index]
        side = sides[side_index]
        other = sides[1 - side_index]
        if target == 0:
            for layer in range(1, source + 1):
                if not set_cell(side, layer, CRYSTAL):
                    conflict = (side_index, layer, side[layer], CRYSTAL)
                    break
        else:
            for layer in range(target, source):
                if not set_cell(side, layer, CRYSTAL):
                    conflict = (side_index, layer, side[layer], CRYSTAL)
                    break
            if conflict is None and not set_cell(side, source, ORDINARY):
                conflict = (side_index, source, side[source], ORDINARY)
        if conflict is not None:
            break
        if not set_cell(other, source, opposite_source):
            conflict = (1 - side_index, source, other[source], opposite_source)
            break

    if conflict is not None:
        return {"conflict": list(conflict), "ok": False}

    pre_rows = [
        [
            post_a[layer + 1] if layer + 1 < len(post_a) else EMPTY,
            post_b[layer + 1],
            post_c[layer + 1],
            post_d[layer + 1],
        ]
        for layer in range(CAP)
    ]
    predecessor = code(pre_rows)
    pred_columns = tuple(column(pre_rows, q) for q in range(4))
    stable = is_stable(pre_rows)
    craftable = tuple(is_craftable_column(value) for value in pred_columns)
    out = push_pin(pre_rows, CAP)
    actual_a = column(out, 0)
    return {
        "predecessor": predecessor,
        "predecessorColumns": list(pred_columns),
        "stable": stable,
        "craftable": list(craftable),
        "actualA": actual_a,
        "output": code(out),
        "postB": "".join(post_b).rstrip(EMPTY),
        "postD": "".join(post_d).rstrip(EMPTY),
        "distance": sum(a != b for a, b in itertools.zip_longest(actual_a, TARGET, fillvalue=EMPTY)),
        "ok": stable and all(craftable) and actual_a == TARGET,
    }


def main() -> None:
    event = compile_corner_event(TARGET, CAP)
    post = event.c7.post_lift_a
    sources = [i for i, cell in enumerate(post) if cell == ORDINARY]
    targets = [i for i, cell in enumerate(TARGET) if cell == ORDINARY]
    mapping = tuple(zip(sources, targets))
    moving = [(source, target) for source, target in mapping if source != target]
    results = []
    hits = []
    for filler in (ORDINARY, PIN):
        for opposite_source in (EMPTY, PIN):
            for assignment in itertools.product((0, 1), repeat=len(moving)):
                result = compile_two_side(
                    post,
                    mapping,
                    assignment,
                    filler=filler,
                    opposite_source=opposite_source,
                )
                record = {
                    "assignment": ["B" if side == 0 else "D" for side in assignment],
                    "filler": filler,
                    "oppositeSource": opposite_source,
                    **result,
                }
                results.append(record)
                if record.get("ok"):
                    hits.append(record)
    results.sort(key=lambda item: (
        0 if item.get("stable") else 1,
        sum(1 for value in item.get("craftable", []) if not value),
        item.get("distance", 10**9),
        str(item.get("assignment")),
    ))
    report = {
        "schemaVersion": 2,
        "target": TARGET,
        "cap": CAP,
        "postLiftA": post,
        "mapping": [list(pair) for pair in mapping],
        "moving": [list(pair) for pair in moving],
        "checked": len(results),
        "hitCount": len(hits),
        "hits": hits,
        "closest": results[:30],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print(json.dumps({
            "schemaVersion": 2,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))
        raise
