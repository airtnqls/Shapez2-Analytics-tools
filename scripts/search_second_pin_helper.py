from __future__ import annotations

import json
import random
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import is_craftable_column
from backend.corner_half.global_predecessor import compile_global_predecessor
from backend.corner_half.structural_ops import cut, rotate, stack, swap
from backend.corner_half.structural_physics import EMPTY, code, column, is_stable, parse, push_pin

TARGET_COLUMN = "SS-S-cS-S-c"
TARGET_HALF = "SS--:SS--:-S--:SS--:-S--:cS--:SS--:-S--:SS--:-S--:cS--"
CAP = len(TARGET_COLUMN)
ALPHABET = "-SPc"


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


def normalized_word(value: str) -> str:
    return value[:CAP].ljust(CAP, EMPTY)


def word_distance(value: str, target: str) -> int:
    a = normalized_word(value)
    b = normalized_word(target)
    return sum(x != y for x, y in zip(a, b))


def best_target_column(rows) -> tuple[int, dict[str, object]]:
    pillars = [column(rows, q) for q in range(4)]
    ranked = sorted(
        (word_distance(value, TARGET_COLUMN), q, value)
        for q, value in enumerate(pillars)
    )
    distance, q, value = ranked[0]
    return distance, {"column": q, "value": value, "pillars": pillars}


def direct_half_extractions(rows):
    for turns in range(4):
        oriented = rotate(rows, turns)
        east, west = cut(oriented, CAP)
        yield {
            "kind": "direct-cut",
            "turns": turns,
            "side": "east",
            "result": code(east),
        }
        yield {
            "kind": "direct-cut",
            "turns": turns,
            "side": "west-rotated",
            "result": code(rotate(west, 2)),
        }


def finalize_with_tower(rows) -> dict[str, object] | None:
    """Find the constant final Swap/Cut that turns an exact Corner into H=(u,T).

    A final Pin cannot itself create the full S^L payload with an S receipt: it
    would produce P+S^(L-1).  The legacy process therefore uses the Pin to make
    the event Corner, then imports the solid tower by one last Swapper.  This
    routine checks that real physical route instead of requiring the Pin output
    to equal the complete Half.
    """
    for route in direct_half_extractions(rows):
        if route["result"] == TARGET_HALF:
            return route

    tower = "S" * CAP
    helpers = [
        ("east:T,-", rows_from_columns((tower, "", "", ""))),
        ("east:-,T", rows_from_columns(("", tower, "", ""))),
        ("east:T,T", rows_from_columns((tower, tower, "", ""))),
        ("west:T,-", rows_from_columns(("", "", tower, ""))),
        ("west:-,T", rows_from_columns(("", "", "", tower))),
        ("west:T,T", rows_from_columns(("", "", tower, tower))),
    ]
    for helper_name, helper in helpers:
        for order_name, left, right in (
            ("current-helper", rows, helper),
            ("helper-current", helper, rows),
        ):
            for output_index, output in enumerate(swap(left, right, CAP)):
                for route in direct_half_extractions(output):
                    if route["result"] == TARGET_HALF:
                        return {
                            "kind": "final-tower-swap",
                            "helper": helper_name,
                            "helperCode": code(helper),
                            "swapOrder": order_name,
                            "swapOutput": output_index,
                            **route,
                        }
    return None


@dataclass(frozen=True)
class Candidate:
    c: str
    d: str


@dataclass(frozen=True)
class SwapConfig:
    state: str
    state_source: str
    helper_side: str
    swap_order: str
    swap_output: int
    pre_pin_turns: int


def helper_rows(candidate: Candidate, side: str):
    c = normalized_word(candidate.c)
    d = normalized_word(candidate.d)
    if side == "east":
        return rows_from_columns((c, d, "", ""))
    if side == "west":
        return rows_from_columns(("", "", c, d))
    raise ValueError(side)


def evaluate(candidate: Candidate, config: SwapConfig) -> tuple[tuple[int, int, int, int, int], dict[str, object]]:
    c = normalized_word(candidate.c)
    d = normalized_word(candidate.d)
    helper = helper_rows(candidate, config.helper_side)
    helper_stable = is_stable(helper)
    c_ok = is_craftable_column(c.rstrip(EMPTY))
    d_ok = is_craftable_column(d.rstrip(EMPTY))

    state = parse(config.state, CAP)
    if config.swap_order == "state-helper":
        outputs = swap(state, helper, CAP)
    else:
        outputs = swap(helper, state, CAP)
    swapped = outputs[config.swap_output]
    pre = rotate(swapped, config.pre_pin_turns)
    pre_stable = is_stable(pre)
    pushed = push_pin(pre, CAP)
    distance, column_info = best_target_column(pushed)
    final_route = finalize_with_tower(pushed) if distance == 0 else None

    penalty = (
        (0 if helper_stable else 80)
        + (0 if pre_stable else 80)
        + (0 if c_ok else 40)
        + (0 if d_ok else 40)
    )
    # If the event Corner is exact but the final tower route is blocked by a
    # crystal cut boundary, keep it close but behind a fully finalizable hit.
    route_penalty = 0 if final_route is not None else (4 if distance == 0 else 0)
    complexity = sum(ch != "S" for ch in c + d)
    support_penalty = sum(ch == EMPTY for ch in c + d)
    score = (distance + penalty + route_penalty, distance, complexity, support_penalty, 0)
    return score, {
        "config": {
            "stateSource": config.state_source,
            "helperSide": config.helper_side,
            "swapOrder": config.swap_order,
            "swapOutput": config.swap_output,
            "prePinTurns": config.pre_pin_turns,
        },
        "state": config.state,
        "statePillars": [column(state, q) for q in range(4)],
        "c": c.rstrip(EMPTY),
        "d": d.rstrip(EMPTY),
        "helper": code(helper),
        "helperStable": helper_stable,
        "preStable": pre_stable,
        "columnsCraftable": [c_ok, d_ok],
        "afterSecondSwap": code(swapped),
        "preFinal": code(pre),
        "preFinalPillars": [column(pre, q) for q in range(4)],
        "afterFinalPin": code(pushed),
        "afterFinalPillars": [column(pushed, q) for q in range(4)],
        "distance": distance,
        "targetColumn": column_info,
        "finalRoute": final_route,
        "score": list(score),
    }


def mutations(candidate: Candidate):
    for which in (0, 1):
        word = list(normalized_word(candidate.c if which == 0 else candidate.d))
        for layer in range(CAP):
            old = word[layer]
            for cell in ALPHABET:
                if cell == old:
                    continue
                changed = word.copy()
                changed[layer] = cell
                value = "".join(changed)
                yield Candidate(value, candidate.d) if which == 0 else Candidate(candidate.c, value)


def seed_words(first) -> list[str]:
    tower = "S" * CAP
    words = {
        "", tower, "c" * CAP, "P" * CAP,
        TARGET_COLUMN,
        first.pushed_columns[0], first.pushed_columns[1], first.pushed_columns[2], first.pushed_columns[3],
        first.predecessor_columns[0], first.predecessor_columns[1], first.predecessor_columns[2], first.predecessor_columns[3],
        # The bottom receipt must be empty for a final S.  Seed the exact family
        # suggested by the unfinished legacy build_pinable_shape2 routine.
        "-" + TARGET_COLUMN[:-1],
        "--" + TARGET_COLUMN[:-2],
    }
    for value in list(words):
        v = normalized_word(value)
        words.update({
            v.replace("P", "S"),
            v.replace("c", "S"),
            v.replace("P", EMPTY),
            v.replace("c", EMPTY),
            EMPTY + v[:-1],
            v[1:] + EMPTY,
        })
    return sorted({normalized_word(value) for value in words})


def first_swap_states(first) -> list[tuple[str, str]]:
    pushed = parse(first.pushed, CAP)
    top_two = parse("---S:---S", CAP)
    stacked = stack(pushed, top_two, CAP)
    tower = "S" * CAP
    helpers = [
        ("east:T,-", rows_from_columns((tower, "", "", ""))),
        ("east:-,T", rows_from_columns(("", tower, "", ""))),
        ("east:T,T", rows_from_columns((tower, tower, "", ""))),
        ("west:T,-", rows_from_columns(("", "", tower, ""))),
        ("west:-,T", rows_from_columns(("", "", "", tower))),
        ("west:T,T", rows_from_columns(("", "", tower, tower))),
    ]
    states: dict[str, str] = {}
    for helper_name, helper in helpers:
        for order_name, left, right in (
            ("current-helper", stacked, helper),
            ("helper-current", helper, stacked),
        ):
            for output_index, output in enumerate(swap(left, right, CAP)):
                for turns in range(4):
                    state = fixed_rows(rotate(output, turns))
                    state_code = code(state)
                    source = f"{helper_name}/{order_name}/out{output_index}/rot{turns}"
                    states.setdefault(state_code, source)
    return sorted(states.items())


def all_configs(first) -> list[SwapConfig]:
    configs: dict[tuple[str, str, str, int, int], SwapConfig] = {}
    for state, source in first_swap_states(first):
        for helper_side in ("east", "west"):
            for swap_order in ("state-helper", "helper-state"):
                for swap_output in (0, 1):
                    for pre_pin_turns in range(4):
                        key = (state, helper_side, swap_order, swap_output, pre_pin_turns)
                        configs[key] = SwapConfig(
                            state, source, helper_side, swap_order, swap_output, pre_pin_turns
                        )
    return list(configs.values())


def search_configuration(config: SwapConfig, first, *, seed: int = 0, beam_width: int = 360, rounds: int = 36):
    words = seed_words(first)
    rng = random.Random(seed)
    initial = {Candidate(c, d) for c in words for d in words}
    for _ in range(5000):
        base_c = list(normalized_word(rng.choice(words)))
        base_d = list(normalized_word(rng.choice(words)))
        for _ in range(rng.randint(1, 6)):
            if rng.random() < 0.5:
                base_c[rng.randrange(CAP)] = rng.choice(ALPHABET)
            else:
                base_d[rng.randrange(CAP)] = rng.choice(ALPHABET)
        initial.add(Candidate("".join(base_c), "".join(base_d)))

    cache: dict[Candidate, tuple[tuple[int, int, int, int, int], dict[str, object]]] = {}

    def measured(candidate: Candidate):
        if candidate not in cache:
            cache[candidate] = evaluate(candidate, config)
        return cache[candidate]

    def select(pool, limit):
        ranked = sorted(
            pool,
            key=lambda c: (measured(c)[0], normalized_word(c.c), normalized_word(c.d)),
        )
        return ranked[:limit]

    beam = select(initial, beam_width)
    exact: list[dict[str, object]] = []
    history = []
    for round_index in range(rounds):
        if not beam:
            break
        best_score, best_record = measured(beam[0])
        history.append({"round": round_index, "score": list(best_score), "best": best_record})
        for candidate in beam:
            _score, record = measured(candidate)
            if (
                record["distance"] == 0
                and record["finalRoute"] is not None
                and record["helperStable"]
                and record["preStable"]
                and all(record["columnsCraftable"])
            ):
                exact.append(record)
        if exact:
            break
        pool = set(beam)
        for candidate in beam:
            pool.update(mutations(candidate))
        beam = select(pool, beam_width)

    closest = [measured(candidate)[1] for candidate in beam[:30]]
    return {
        "config": {
            "stateSource": config.state_source,
            "helperSide": config.helper_side,
            "swapOrder": config.swap_order,
            "swapOutput": config.swap_output,
            "prePinTurns": config.pre_pin_turns,
        },
        "evaluated": len(cache),
        "rounds": len(history),
        "history": history,
        "exact": exact[:20],
        "closest": closest,
    }


def main() -> None:
    first = compile_global_predecessor(TARGET_COLUMN, CAP)
    configs = all_configs(first)

    probe_candidates = [
        Candidate("S" * CAP, "S" * CAP),
        Candidate("c" * CAP, "S" * CAP),
        Candidate("S" * CAP, "c" * CAP),
        Candidate(first.predecessor_columns[2], first.predecessor_columns[3]),
        Candidate(first.pushed_columns[2], first.pushed_columns[3]),
        Candidate("-" + TARGET_COLUMN[:-1], "S" * CAP),
    ]
    ranked = []
    for config in configs:
        best = min(evaluate(candidate, config)[0] for candidate in probe_candidates)
        ranked.append((best, config))
    ranked.sort(
        key=lambda item: (
            item[0], item[1].state, item[1].helper_side,
            item[1].swap_order, item[1].swap_output, item[1].pre_pin_turns,
        )
    )
    selected = [item[1] for item in ranked[:32]]

    searches = []
    exact = []
    for index, config in enumerate(selected):
        result = search_configuration(config, first, seed=index)
        searches.append(result)
        exact.extend(result["exact"])
        if exact:
            break

    closest = sorted(
        (record for result in searches for record in result["closest"]),
        key=lambda record: (tuple(record["score"]), record["config"], record["c"], record["d"]),
    )[:50]
    report = {
        "schemaVersion": 4,
        "target": TARGET_HALF,
        "targetColumn": TARGET_COLUMN,
        "firstPredecessor": first.predecessor,
        "afterFirstPin": first.pushed,
        "firstStates": len(first_swap_states(first)),
        "swapConfigurations": len(configs),
        "selectedConfigurations": [
            {
                "stateSource": item.state_source,
                "helperSide": item.helper_side,
                "swapOrder": item.swap_order,
                "swapOutput": item.swap_output,
                "prePinTurns": item.pre_pin_turns,
            }
            for item in selected
        ],
        "searches": searches,
        "exact": exact[:20],
        "closest": closest,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        print(json.dumps({
            "schemaVersion": 4,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))
        raise
