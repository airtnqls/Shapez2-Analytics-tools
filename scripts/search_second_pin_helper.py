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


def target_distance(rows) -> tuple[int, dict[str, object]]:
    target = fixed_rows(parse(TARGET_HALF, CAP))
    best = (10**9, {})
    for turns in range(4):
        oriented = rotate(rows, turns)
        east, west = cut(oriented, CAP)
        for side, raw_candidate in (("east", east), ("west", rotate(west, 2))):
            candidate = fixed_rows(raw_candidate)
            distance = 0
            for layer in range(CAP):
                for q in range(2):
                    if candidate[layer][q] != target[layer][q]:
                        distance += 1
            if distance < best[0]:
                best = (distance, {
                    "turns": turns,
                    "side": side,
                    "candidate": code(candidate),
                    "candidatePillars": [column(candidate, q) for q in range(4)],
                })
    return best


@dataclass(frozen=True)
class Candidate:
    c: str
    d: str


@dataclass(frozen=True)
class FixedHalf:
    first: str
    second: str
    source: str


def evaluate(candidate: Candidate, fixed_half: FixedHalf) -> tuple[tuple[int, int, int, int], dict[str, object]]:
    c = normalized_word(candidate.c)
    d = normalized_word(candidate.d)
    helper_rows = rows_from_columns(("", "", c, d))
    helper_stable = is_stable(helper_rows)
    c_ok = is_craftable_column(c.rstrip(EMPTY))
    d_ok = is_craftable_column(d.rstrip(EMPTY))
    pre = rows_from_columns((fixed_half.first, fixed_half.second, c, d))
    pre_stable = is_stable(pre)
    pushed = push_pin(pre, CAP)
    distance, extraction = target_distance(pushed)
    penalty = (0 if helper_stable else 40) + (0 if pre_stable else 40) + (0 if c_ok else 20) + (0 if d_ok else 20)
    complexity = sum(ch != "S" for ch in c + d)
    score = (distance + penalty, distance, complexity, 0)
    return score, {
        "fixedHalf": [fixed_half.first, fixed_half.second],
        "fixedHalfSource": fixed_half.source,
        "c": c.rstrip(EMPTY),
        "d": d.rstrip(EMPTY),
        "helper": code(helper_rows),
        "helperStable": helper_stable,
        "preStable": pre_stable,
        "columnsCraftable": [c_ok, d_ok],
        "preFinal": code(pre),
        "preFinalPillars": [column(pre, q) for q in range(4)],
        "afterFinalPin": code(pushed),
        "afterFinalPillars": [column(pushed, q) for q in range(4)],
        "distance": distance,
        "score": list(score),
        "extraction": extraction,
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
    }
    for value in list(words):
        v = normalized_word(value)
        words.update({
            v.replace("P", "S"), v.replace("c", "S"), v.replace("P", EMPTY), v.replace("c", EMPTY),
            EMPTY + v[:-1], v[1:] + EMPTY,
        })
    return sorted({normalized_word(value) for value in words})


def first_swap_fixed_halves(first) -> list[FixedHalf]:
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
    states: dict[str, tuple[list[list[str]], str]] = {}
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
                    states.setdefault(state_code, (state, source))

    fixed: dict[tuple[str, str], FixedHalf] = {}
    for state, source in states.values():
        values = tuple(column(state, q) for q in range(4))
        for turns in range(4):
            rotated_values = values[(-turns) % 4:] + values[:(-turns) % 4] if turns else values
            for offset in range(4):
                a = rotated_values[offset]
                b = rotated_values[(offset + 1) % 4]
                key = (a, b)
                fixed.setdefault(key, FixedHalf(a, b, f"{source}/pair{offset}/extra-rot{turns}"))
    # Keep only halves that could plausibly survive a final Pin: at least one
    # column carries target/event content or is the full-S payload.
    return sorted(
        (
            item for item in fixed.values()
            if item.first or item.second
        ),
        key=lambda item: (item.first, item.second, item.source),
    )


def search_configuration(fixed_half: FixedHalf, first, *, seed: int = 0, beam_width: int = 240, rounds: int = 24):
    words = seed_words(first)
    rng = random.Random(seed)
    initial = {Candidate(c, d) for c in words for d in words}
    for _ in range(2500):
        base_c = list(normalized_word(rng.choice(words)))
        base_d = list(normalized_word(rng.choice(words)))
        for _ in range(rng.randint(1, 4)):
            base_c[rng.randrange(CAP)] = rng.choice(ALPHABET)
            base_d[rng.randrange(CAP)] = rng.choice(ALPHABET)
        initial.add(Candidate("".join(base_c), "".join(base_d)))

    cache: dict[Candidate, tuple[tuple[int, int, int, int], dict[str, object]]] = {}

    def measured(candidate: Candidate):
        if candidate not in cache:
            cache[candidate] = evaluate(candidate, fixed_half)
        return cache[candidate]

    def select(pool, limit):
        ranked = sorted(pool, key=lambda c: (measured(c)[0], normalized_word(c.c), normalized_word(c.d)))
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
            score, record = measured(candidate)
            if score[1] == 0 and record["helperStable"] and record["preStable"] and all(record["columnsCraftable"]):
                exact.append(record)
        if exact:
            break
        pool = set(beam)
        for candidate in beam:
            pool.update(mutations(candidate))
        beam = select(pool, beam_width)

    closest = [measured(candidate)[1] for candidate in beam[:30]]
    return {
        "fixedHalf": [fixed_half.first, fixed_half.second],
        "fixedHalfSource": fixed_half.source,
        "evaluated": len(cache),
        "rounds": len(history),
        "history": history,
        "exact": exact[:20],
        "closest": closest,
    }


def main() -> None:
    first = compile_global_predecessor(TARGET_COLUMN, CAP)
    fixed_halves = first_swap_fixed_halves(first)

    # Rank fixed halves by a cheap all-S/all-c seed evaluation, then spend the
    # beam budget only on the most promising constant number of orientations.
    probe_candidates = [Candidate("S" * CAP, "S" * CAP), Candidate("c" * CAP, "S" * CAP), Candidate("S" * CAP, "c" * CAP)]
    ranked = []
    for fixed_half in fixed_halves:
        best = min(evaluate(candidate, fixed_half)[0] for candidate in probe_candidates)
        ranked.append((best, fixed_half))
    ranked.sort(key=lambda item: (item[0], item[1].first, item[1].second, item[1].source))
    selected = [item[1] for item in ranked[:12]]

    searches = []
    exact = []
    for index, fixed_half in enumerate(selected):
        result = search_configuration(fixed_half, first, seed=index)
        searches.append(result)
        exact.extend(result["exact"])
        if exact:
            break

    closest = sorted(
        (record for result in searches for record in result["closest"]),
        key=lambda record: (tuple(record["score"]), record["fixedHalf"], record["c"], record["d"]),
    )[:50]
    report = {
        "schemaVersion": 2,
        "target": TARGET_HALF,
        "targetColumn": TARGET_COLUMN,
        "firstPredecessor": first.predecessor,
        "afterFirstPin": first.pushed,
        "fixedHalfCandidates": len(fixed_halves),
        "selectedFixedHalves": [[item.first, item.second, item.source] for item in selected],
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
            "schemaVersion": 2,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, indent=2))
        raise
