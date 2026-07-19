"""Run inside Shapez2-Analytics-tools to compare its real Shape API to core.

Usage after copying/installing this package into the repository::

    PYTHONPATH=src python scripts/legacy_differential.py --cases 10000

Only stable operation inputs are compared, which is the domain of game
operations.  Structural equality intentionally ignores color and ordinary
subtype.
"""
from __future__ import annotations

import argparse
import json
import random
import time

from shape import Shape
from shapez2_core import (
    CompactShape,
    CutAxis,
    apply_gravity,
    crystal_generator,
    cut,
    from_legacy_shape,
    pin_push,
    rotate,
    stack,
    swap,
    to_legacy_shape,
)


def _legacy(shape: CompactShape):
    result = to_legacy_shape(shape)
    result.max_layers = shape.cap
    return result


def _compact(value, cap: int) -> CompactShape:
    return from_legacy_shape(value, cap=cap)


def run(cases: int, seed: int, max_cap: int) -> dict:
    rng = random.Random(seed)
    started = time.perf_counter()
    checked = 0
    old_global = Shape.MAX_LAYERS
    try:
        for _ in range(cases):
            cap = rng.randint(1, max_cap)
            Shape.MAX_LAYERS = cap
            a = apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
            b = apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
            la, lb = _legacy(a), _legacy(b)

            assert _compact(la.apply_physics(), cap) == a
            assert _compact(la.rotate(clockwise=True), cap) == rotate(a, 1)
            assert _compact(la.rotate(clockwise=False), cap) == rotate(a, 3)
            assert _compact(la.push_pin(), cap) == pin_push(a)
            if not a.is_empty:
                # The legacy project creates a crystal layer for an empty object;
                # the authoritative game/cpcp semantics leave height-0 empty.
                assert _compact(la.crystal_generator("w"), cap) == crystal_generator(a)
            assert _compact(Shape.stack(la, lb), cap) == stack(a, b)

            # Repository half_cutter uses horizontal=False/True.
            # Legacy half_cutter returns (west, east), while the authoritative
            # cpcp/core API returns (east, west).
            west, east = la.half_cutter(horizontal=False)
            assert (_compact(east, cap), _compact(west, cap)) == cut(a, CutAxis.VERTICAL)
            north, south = la.half_cutter(horizontal=True)
            assert (_compact(north, cap), _compact(south, cap)) == cut(a, CutAxis.HORIZONTAL)

            out0, out1 = Shape.swap(la, lb)
            assert (_compact(out0, cap), _compact(out1, cap)) == swap(a, b, CutAxis.VERTICAL)
            checked += 1
    finally:
        Shape.MAX_LAYERS = old_global

    return {
        "status": "PASS",
        "cases": checked,
        "seed": seed,
        "max_cap": max_cap,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--max-cap", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(run(args.cases, args.seed, args.max_cap), indent=2))


if __name__ == "__main__":
    main()
