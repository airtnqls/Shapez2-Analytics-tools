from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.structural_ops import cut, rotate, stack, swap
from backend.corner_half.structural_physics import EMPTY, ORDINARY, code, column, is_stable, parse, push_pin
from scripts.audit_user_legacy_macro import CAP, PILLAR, TARGET, build_pinable_shape


def rows_from_columns(values: tuple[str, str, str, str]):
    return [
        [values[q][layer] if layer < len(values[q]) else EMPTY for q in range(4)]
        for layer in range(CAP)
    ]


def columns(rows) -> tuple[str, str, str, str]:
    return tuple(column(rows, q) for q in range(4))


def helper_half(first: str, second: str, side: str):
    if side == "east":
        values = (first, second, "", "")
    else:
        values = ("", "", first, second)
    rows = rows_from_columns(values)
    return rows if is_stable(rows) else None


def target_from_any_half(rows):
    hits = []
    for turns in range(4):
        oriented = rotate(rows, turns)
        east, west = cut(oriented, CAP)
        if code(east) == TARGET:
            hits.append({"turns": turns, "side": "east"})
        if code(rotate(west, 2)) == TARGET:
            hits.append({"turns": turns, "side": "west-rotated"})
    return hits


def variants(value: str) -> set[str]:
    out = {value.rstrip(EMPTY)}
    out.add(value.replace("P", "S").rstrip(EMPTY))
    out.add(value.replace("c", "S").rstrip(EMPTY))
    out.add(value.replace("P", "S").replace("c", "S").rstrip(EMPTY))
    out.add(value.replace("P", EMPTY).rstrip(EMPTY))
    out.add(value.replace("c", EMPTY).rstrip(EMPTY))
    out.add((EMPTY + value[: CAP - 1]).rstrip(EMPTY))
    out.add(value[1:].rstrip(EMPTY))
    return out


def first_helper_pool(tower: str):
    specs = []
    for side in ("east", "west"):
        for pair in ((tower, ""), ("", tower), (tower, tower)):
            helper = helper_half(pair[0], pair[1], side)
            if helper is not None:
                specs.append((side, pair, helper))
    return specs


def half_distance(rows) -> tuple[int, dict[str, object]]:
    target_rows = parse(TARGET, CAP)
    best = (10**9, {})
    # Every adjacent ordered pair can be rotated into the east half.  Compare
    # the exact cells before Cutter so the rank also exposes near misses.
    for turns in range(4):
        oriented = rotate(rows, turns)
        for side, pair in (("east", (0, 1)), ("west", (2, 3))):
            candidate = rows_from_columns((column(oriented, pair[0]), column(oriented, pair[1]), "", ""))
            if side == "west":
                candidate = rotate(candidate, 2)
            distance = 0
            for layer in range(CAP):
                for q in range(2):
                    if candidate[layer][q] != target_rows[layer][q]:
                        distance += 1
            record = {
                "turns": turns,
                "side": side,
                "candidate": code(candidate),
                "candidatePillars": columns(candidate),
            }
            if distance < best[0]:
                best = (distance, record)
    return best


def main() -> None:
    predecessor = parse(build_pinable_shape(PILLAR, CAP), CAP)
    pushed = push_pin(predecessor, CAP)
    top_two = parse("---S:---S", CAP)
    stacked = stack(pushed, top_two, CAP)

    tower = ORDINARY * CAP
    word_set = {"", tower, "c" * CAP, "P" * CAP}
    for source in (predecessor, pushed, stacked, parse(TARGET, CAP)):
        for word in columns(source):
            word_set.update(variants(word))
    words = sorted(word_set)

    second_helpers = []
    for side in ("east", "west"):
        for first in words:
            for second in words:
                helper = helper_half(first, second, side)
                if helper is not None:
                    second_helpers.append((side, first, second, helper))

    first_states: dict[str, dict[str, object]] = {}
    for side, pair, helper in first_helper_pool(tower):
        for order in ("current-helper", "helper-current"):
            operands = (stacked, helper) if order == "current-helper" else (helper, stacked)
            outputs = swap(*operands, CAP)
            for output_index, output in enumerate(outputs):
                for turns in range(4):
                    state = rotate(output, turns)
                    first_states.setdefault(code(state), {
                        "firstHelperSide": side,
                        "firstHelperColumns": list(pair),
                        "firstHelper": code(helper),
                        "firstSwapOrder": order,
                        "firstSwapOutput": output_index,
                        "middleTurns": turns,
                        "state": code(state),
                        "pillars": columns(state),
                    })

    hits = []
    closest_heap: list[tuple[int, int, dict[str, object]]] = []
    serial = 0
    tested = 0
    for first in first_states.values():
        state = parse(str(first["state"]), CAP)
        for side, a, b, helper in second_helpers:
            for order in ("current-helper", "helper-current"):
                operands = (state, helper) if order == "current-helper" else (helper, state)
                for output_index, output in enumerate(swap(*operands, CAP)):
                    tested += 1
                    pushed_final = push_pin(output, CAP)
                    finals = target_from_any_half(pushed_final)
                    base = {
                        **first,
                        "secondHelperSide": side,
                        "secondHelperColumns": [a, b],
                        "secondHelper": code(helper),
                        "secondSwapOrder": order,
                        "secondSwapOutput": output_index,
                        "preFinalPin": code(output),
                        "preFinalPillars": columns(output),
                        "postFinalPin": code(pushed_final),
                        "postFinalPillars": columns(pushed_final),
                    }
                    if finals:
                        hits.append({**base, "finalExtraction": finals})
                    distance, nearest = half_distance(pushed_final)
                    ranked = {**base, "distance": distance, "nearest": nearest}
                    serial += 1
                    entry = (-distance, serial, ranked)
                    if len(closest_heap) < 100:
                        heapq.heappush(closest_heap, entry)
                    elif entry > closest_heap[0]:
                        heapq.heapreplace(closest_heap, entry)

    closest = [entry[2] for entry in sorted(closest_heap, key=lambda x: (-x[0], x[1]))]
    report = {
        "schemaVersion": 3,
        "sequence": ["PIN_PUSH", "STACK(q3,Sx2)", "SWAP", "ROTATE", "SWAP", "PIN_PUSH", "CUT/ROTATE"],
        "predecessor": code(predecessor),
        "afterFirstPin": code(pushed),
        "afterStack": code(stacked),
        "afterStackPillars": columns(stacked),
        "candidateWords": len(words),
        "secondHelpers": len(second_helpers),
        "firstStates": len(first_states),
        "firstStateDetails": list(first_states.values()),
        "testedSecondSwapOutputs": tested,
        "hits": hits[:100],
        "closest": closest,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
