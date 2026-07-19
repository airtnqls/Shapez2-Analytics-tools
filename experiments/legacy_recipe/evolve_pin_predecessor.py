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

from legacy_corner_recipe import (  # noqa: E402
    TARGET_CODE,
    TARGET_LEFT_PILLAR,
    Shape,
    structural,
)

with contextlib.redirect_stdout(io.StringIO()):
    from corner_tracer import build_pinable_shape  # noqa: E402

ALPHABET = ("-", "S", "P", "c")


def rows(code: str, cap: int) -> list[list[str]]:
    parsed = [list(x) for x in code.split(":") if x]
    while len(parsed) < cap:
        parsed.append(list("----"))
    return parsed[:cap]


def encode(grid: list[list[str]]) -> str:
    out = ["".join(r) for r in grid]
    while out and out[-1] == "----":
        out.pop()
    return ":".join(out)


def from_struct(code: str, cap: int) -> Shape:
    shape = Shape.from_string(code)
    shape.max_layers = cap
    return shape


def normalize_source(code: str, cap: int) -> str:
    shape = from_struct(code, cap)
    normalized = shape.apply_physics()
    normalized.max_layers = cap
    return structural(normalized)


def diff(output: str, goal: str) -> dict[str, int]:
    oa = rows(output, len(TARGET_LEFT_PILLAR))
    ga = rows(goal, len(TARGET_LEFT_PILLAR))
    mismatch = unwanted_p = missing_c = unwanted_c = missing_s = extra_piece = 0
    for orow, grow in zip(oa, ga):
        for x, y in zip(orow, grow):
            if x == y:
                continue
            mismatch += 1
            unwanted_p += x == "P"
            missing_c += y == "c" and x != "c"
            unwanted_c += x == "c" and y != "c"
            missing_s += y == "S" and x != "S"
            extra_piece += y == "-" and x != "-"
    return {
        "mismatch": int(mismatch),
        "unwanted_p": int(unwanted_p),
        "missing_c": int(missing_c),
        "unwanted_c": int(unwanted_c),
        "missing_s": int(missing_s),
        "extra_piece": int(extra_piece),
    }


def rank(d: dict[str, int], source_code: str) -> tuple[int, int, int, int, int]:
    weighted = (
        12 * d["mismatch"]
        + 12 * d["missing_c"]
        + 5 * d["unwanted_c"]
        + 4 * d["unwanted_p"]
        + 2 * d["extra_piece"]
    )
    source_cells = sum(ch != "-" for ch in source_code if ch != ":")
    return weighted, d["mismatch"], d["missing_c"], d["unwanted_p"], source_cells


@dataclass(frozen=True)
class Evaluation:
    source: str
    output: str
    distance: dict[str, int]
    score: tuple[int, int, int, int, int]


def evaluate(code: str, goal: str, cap: int, cache: dict[str, Evaluation]) -> Evaluation:
    stable_code = normalize_source(code, cap)
    if stable_code in cache:
        return cache[stable_code]
    source = from_struct(stable_code, cap)
    output = structural(source.push_pin())
    d = diff(output, goal)
    value = Evaluation(stable_code, output, d, rank(d, stable_code))
    cache[stable_code] = value
    return value


def shifted_target_seed(goal: str, cap: int) -> str:
    """Rough inverse seed: shift target one row down and add support columns."""
    g = rows(goal, cap)
    source = [list("SSSS") for _ in range(cap)]
    for layer in range(cap - 1):
        for q in range(4):
            target_piece = g[layer + 1][q]
            source[layer][q] = target_piece if target_piece != "P" else "S"
    source[-1] = list("----")
    return encode(source)


def initial_seeds(goal: str, cap: int) -> list[str]:
    with contextlib.redirect_stdout(io.StringIO()):
        legacy = build_pinable_shape(TARGET_LEFT_PILLAR)
    seeds = [legacy, shifted_target_seed(goal, cap)]
    legacy_grid = rows(legacy, cap)

    # Systematic scaffold removal/retention variants.
    for keep_mask in range(1, 16):
        grid = [r[:] for r in legacy_grid]
        for layer in range(cap):
            for q in range(4):
                if not (keep_mask & (1 << q)):
                    grid[layer][q] = "-"
        seeds.append(encode(grid))

    # Hybrid seeds: target-shifted q0/q1 with legacy sacrificial supports.
    shifted = rows(shifted_target_seed(goal, cap), cap)
    for mask in (1, 2, 3):
        grid = [r[:] for r in legacy_grid]
        for layer in range(cap):
            for q in range(2):
                if mask & (1 << q):
                    grid[layer][q] = shifted[layer][q]
        seeds.append(encode(grid))

    return seeds


def single_cell_neighbors(code: str, cap: int, focus: list[tuple[int, int]] | None = None):
    grid = rows(code, cap)
    coords = focus if focus is not None else [(l, q) for l in range(cap) for q in range(4)]
    for layer, q in coords:
        old = grid[layer][q]
        for value in ALPHABET:
            if value == old:
                continue
            mutated = [r[:] for r in grid]
            mutated[layer][q] = value
            yield encode(mutated)


def output_focus(output: str, goal: str, cap: int) -> list[tuple[int, int]]:
    """Map output mismatches to nearby predecessor rows/cells."""
    out = rows(output, cap)
    target = rows(goal, cap)
    coords = set()
    for layer in range(cap):
        for q in range(4):
            if out[layer][q] != target[layer][q]:
                for source_layer in (layer - 2, layer - 1, layer, layer + 1):
                    if 0 <= source_layer < cap:
                        coords.add((source_layer, q))
                        coords.add((source_layer, (q - 1) % 4))
                        coords.add((source_layer, (q + 1) % 4))
    return sorted(coords)


def random_mutations(code: str, cap: int, rng: random.Random, count: int, edits: int):
    base = rows(code, cap)
    for _ in range(count):
        grid = [r[:] for r in base]
        for _ in range(edits):
            layer = rng.randrange(cap)
            q = rng.randrange(4)
            grid[layer][q] = rng.choice(ALPHABET)
        yield encode(grid)


def search(
    *,
    seed: int = 20260719,
    beam_width: int = 64,
    elite_count: int = 10,
    max_generations: int = 200,
    max_seconds: float = 80.0,
    max_evaluations: int = 50000,
) -> dict:
    started = time.perf_counter()
    rng = random.Random(seed)
    cap = len(TARGET_LEFT_PILLAR)
    Shape.MAX_LAYERS = cap
    goal_shape = from_struct(TARGET_CODE, cap)
    goal = structural(goal_shape)
    cache: dict[str, Evaluation] = {}

    population = [evaluate(code, goal, cap, cache) for code in initial_seeds(goal, cap)]
    population = sorted({x.source: x for x in population}.values(), key=lambda x: x.score)[:beam_width]
    history = []
    hit = None
    stop_reason = "generation-limit"

    for generation in range(max_generations):
        population.sort(key=lambda x: x.score)
        best = population[0]
        history.append(
            {
                "generation": generation,
                "evaluations": len(cache),
                "best_score": best.score,
                "best_distance": best.distance,
                "best_source": best.source,
                "best_output": best.output,
            }
        )
        if best.output == goal:
            hit = best
            stop_reason = "hit"
            break
        if time.perf_counter() - started >= max_seconds:
            stop_reason = "time-limit"
            break
        if len(cache) >= max_evaluations:
            stop_reason = "evaluation-limit"
            break

        proposals = {}
        for elite in population[:elite_count]:
            focus = output_focus(elite.output, goal, cap)
            # Exact local coordinate descent around every current mismatch.
            for code in single_cell_neighbors(elite.source, cap, focus):
                proposals[code] = None
            # Escapes for support/shatter interactions.
            for edits, count in ((2, 80), (3, 40), (5, 16)):
                for code in random_mutations(elite.source, cap, rng, count, edits):
                    proposals[code] = None

        # Row-wise crossover between elites.
        elites = population[:elite_count]
        for i, a in enumerate(elites):
            ag = rows(a.source, cap)
            for b in elites[i + 1 :]:
                bg = rows(b.source, cap)
                for cut in range(1, cap):
                    proposals[encode(ag[:cut] + bg[cut:])] = None
                    proposals[encode(bg[:cut] + ag[cut:])] = None

        evaluated = []
        for code in proposals:
            evaluated.append(evaluate(code, goal, cap, cache))
            if len(cache) >= max_evaluations or time.perf_counter() - started >= max_seconds:
                break
        population = sorted(
            {x.source: x for x in population + evaluated}.values(), key=lambda x: x.score
        )[:beam_width]

    population.sort(key=lambda x: x.score)
    best = population[0]
    return {
        "schema_version": 1,
        "goal": goal,
        "parameters": {
            "seed": seed,
            "beam_width": beam_width,
            "elite_count": elite_count,
            "max_generations": max_generations,
            "max_seconds": max_seconds,
            "max_evaluations": max_evaluations,
        },
        "stop_reason": stop_reason,
        "elapsed_seconds": time.perf_counter() - started,
        "evaluations": len(cache),
        "hit": None
        if hit is None
        else {
            "source": hit.source,
            "output": hit.output,
            "distance": hit.distance,
            "score": hit.score,
        },
        "best": {
            "source": best.source,
            "output": best.output,
            "distance": best.distance,
            "score": best.score,
        },
        "history": history[-20:],
    }


if __name__ == "__main__":
    print(json.dumps(search(), ensure_ascii=False, indent=2))
