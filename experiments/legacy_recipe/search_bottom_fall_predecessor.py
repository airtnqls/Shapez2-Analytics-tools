from __future__ import annotations

import contextlib
import io
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolve_pin_predecessor import (  # noqa: E402
    ALPHABET,
    Evaluation,
    diff,
    encode,
    from_struct,
    rank,
    rows,
)
from legacy_corner_recipe import TARGET_CODE, TARGET_LEFT_PILLAR, Shape, structural  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    from corner_tracer import build_pinable_shape  # noqa: E402

CAP = len(TARGET_LEFT_PILLAR)


def normalize_constrained(code: str) -> str | None:
    shape = from_struct(code, CAP)
    stable = shape.apply_physics()
    stable.max_layers = CAP
    normalized = structural(stable)
    grid = rows(normalized, CAP)
    # Exact necessary condition for avoiding new bottom pins in target columns.
    if grid[0][0] != "-" or grid[0][1] != "-":
        return None
    return normalized


def evaluate_constrained(code: str, goal: str, cache: dict[str, Evaluation]) -> Evaluation | None:
    stable = normalize_constrained(code)
    if stable is None:
        return None
    if stable in cache:
        return cache[stable]
    output = structural(from_struct(stable, CAP).push_pin())
    d = diff(output, goal)
    value = Evaluation(stable, output, d, rank(d, stable))
    cache[stable] = value
    return value


def seed_shapes(goal: str) -> list[str]:
    with contextlib.redirect_stdout(io.StringIO()):
        legacy = build_pinable_shape(TARGET_LEFT_PILLAR)
    lg = rows(legacy, CAP)
    seeds = []

    # Clear target bottom columns while preserving legacy sacrificial supports.
    for bottom_template in ("--SS", "--cS", "--Sc", "--cc", "---S", "--S-"):
        grid = [r[:] for r in lg]
        grid[0] = list(bottom_template)
        seeds.append(encode(grid))

    # Shift target rows, attach full support columns q2/q3, and vary event/P
    # scaffolding in the target columns.
    target = rows(goal, CAP)
    for support in ("SS", "Sc", "cS", "cc"):
        grid = [list("----") for _ in range(CAP)]
        grid[0] = list("--" + support)
        for layer in range(1, CAP):
            previous = target[layer - 1]
            grid[layer][0] = previous[0]
            grid[layer][1] = previous[1]
            grid[layer][2] = support[0]
            grid[layer][3] = support[1]
        seeds.append(encode(grid))

    # Piecewise combine shifted target with the proven legacy scaffold.
    for split in range(1, CAP):
        shifted = [list("----") for _ in range(CAP)]
        shifted[0] = list("--cS")
        for layer in range(1, CAP):
            shifted[layer][0] = target[layer - 1][0]
            shifted[layer][1] = target[layer - 1][1]
            shifted[layer][2:] = lg[layer][2:]
        grid = [lg[i][:] if i >= split else shifted[i][:] for i in range(CAP)]
        grid[0][0] = grid[0][1] = "-"
        seeds.append(encode(grid))
    return seeds


def mismatch_focus(output: str, goal: str) -> list[tuple[int, int]]:
    out = rows(output, CAP)
    target = rows(goal, CAP)
    focus = set()
    for layer in range(CAP):
        for q in range(4):
            if out[layer][q] == target[layer][q]:
                continue
            # Push shifts source one level upward, while fall/shatter may involve
            # local vertical and adjacent support cells.
            for source_layer in range(max(0, layer - 3), min(CAP, layer + 2)):
                for dq in (-1, 0, 1, 2):
                    focus.add((source_layer, (q + dq) % 4))
    focus.discard((0, 0))
    focus.discard((0, 1))
    return sorted(focus)


def mutate_single(code: str, focus: list[tuple[int, int]]):
    grid = rows(code, CAP)
    for layer, q in focus:
        old = grid[layer][q]
        for value in ALPHABET:
            if value == old:
                continue
            new = [r[:] for r in grid]
            new[layer][q] = value
            new[0][0] = new[0][1] = "-"
            yield encode(new)


def mutate_random(code: str, rng: random.Random, count: int, edits: int):
    base = rows(code, CAP)
    coords = [(l, q) for l in range(CAP) for q in range(4) if not (l == 0 and q in (0, 1))]
    for _ in range(count):
        grid = [r[:] for r in base]
        for _ in range(edits):
            layer, q = rng.choice(coords)
            grid[layer][q] = rng.choice(ALPHABET)
        grid[0][0] = grid[0][1] = "-"
        yield encode(grid)


def search(
    *,
    seed: int = 20260720,
    beam_width: int = 80,
    elite_count: int = 12,
    max_seconds: float = 120.0,
    max_evaluations: int = 90000,
) -> dict:
    started = time.perf_counter()
    rng = random.Random(seed)
    Shape.MAX_LAYERS = CAP
    goal = structural(from_struct(TARGET_CODE, CAP))
    cache: dict[str, Evaluation] = {}

    initial = []
    for code in seed_shapes(goal):
        value = evaluate_constrained(code, goal, cache)
        if value is not None:
            initial.append(value)
    if not initial:
        return {"schema_version": 1, "stop_reason": "no-stable-seeds", "hit": None}
    population = sorted({x.source: x for x in initial}.values(), key=lambda x: x.score)[:beam_width]
    history = []
    hit = None
    generation = 0
    stop_reason = "time-limit"

    while time.perf_counter() - started < max_seconds and len(cache) < max_evaluations:
        population.sort(key=lambda x: x.score)
        best = population[0]
        history.append(
            {
                "generation": generation,
                "evaluations": len(cache),
                "score": best.score,
                "distance": best.distance,
                "source": best.source,
                "output": best.output,
            }
        )
        if best.output == goal:
            hit = best
            stop_reason = "hit"
            break

        proposals = {}
        for elite in population[:elite_count]:
            focus = mismatch_focus(elite.output, goal)
            for code in mutate_single(elite.source, focus):
                proposals[code] = None
            for edits, count in ((2, 120), (3, 70), (5, 30), (8, 10)):
                for code in mutate_random(elite.source, rng, count, edits):
                    proposals[code] = None

        evaluated = []
        for code in proposals:
            value = evaluate_constrained(code, goal, cache)
            if value is not None:
                evaluated.append(value)
            if len(cache) >= max_evaluations or time.perf_counter() - started >= max_seconds:
                break
        population = sorted(
            {x.source: x for x in population + evaluated}.values(), key=lambda x: x.score
        )[:beam_width]
        generation += 1
        if not evaluated:
            stop_reason = "no-new-stable-candidates"
            break

    best = sorted(population, key=lambda x: x.score)[0]
    return {
        "schema_version": 1,
        "necessary_constraint": "stable source bottom q0=q1=empty",
        "parameters": {
            "seed": seed,
            "beam_width": beam_width,
            "elite_count": elite_count,
            "max_seconds": max_seconds,
            "max_evaluations": max_evaluations,
        },
        "stop_reason": stop_reason,
        "elapsed_seconds": time.perf_counter() - started,
        "evaluations": len(cache),
        "generations": generation,
        "hit": None
        if hit is None
        else {"source": hit.source, "output": hit.output, "distance": hit.distance, "score": hit.score},
        "best": {"source": best.source, "output": best.output, "distance": best.distance, "score": best.score},
        "history_tail": history[-10:],
    }


if __name__ == "__main__":
    print(json.dumps(search(), ensure_ascii=False, indent=2))
