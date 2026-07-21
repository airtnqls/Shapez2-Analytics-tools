from __future__ import annotations

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
    # Enumerate the small constant family visible in the screenshot: a stable
    # Half made from zero, one, or two full S towers, in either side.  Keep both
    # operand orders because the selected Swapper output is order-sensitive.
    specs = []
    for side in ("east", "west"):
        for pair in ((tower, ""), ("", tower), (tower, tower)):
            helper = helper_half(pair[0], pair[1], side)
            if helper is not None:
                specs.append((side, pair, helper))
    return specs


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
                    if finals:
                        hits.append({
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
                            "finalExtraction": finals,
                        })
                        if len(hits) >= 100:
                            break
                if len(hits) >= 100:
                    break
            if len(hits) >= 100:
                break
        if len(hits) >= 100:
            break

    report = {
        "schemaVersion": 2,
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
        "hits": hits,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
