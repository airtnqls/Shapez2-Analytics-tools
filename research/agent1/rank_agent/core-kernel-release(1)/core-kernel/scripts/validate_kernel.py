"""Standalone exhaustive/random validation report generator.

The audit is intentionally split:

* exhaustive cap<=2 comparison against an independent reference;
* medium-cap binary-operation differential tests;
* larger-cap differential samples;
* high-cap packed-kernel algebraic/property checks.
"""
from __future__ import annotations

import argparse
import gc
import json
import random
import time
from pathlib import Path

from shapez2_core import CompactShape
from shapez2_core import kernel as fast
from shapez2_core import reference as slow


def _progress(label: str, started: float) -> None:
    print(f"{label}: {time.perf_counter() - started:.3f}s", flush=True)


def run(
    *,
    medium_cases: int,
    large_differential_cases: int,
    high_property_cases: int,
    seed: int,
) -> dict:
    started = time.perf_counter()
    counts = {
        "support_exhaustive": 0,
        "gravity_exhaustive": 0,
        "unary_exhaustive": 0,
        "binary_medium_differential": 0,
        "binary_large_differential": 0,
        "high_cap_properties": 0,
        "stack_compact_equivalence": 0,
    }

    for cap in (1, 2):
        for bits in range(1 << (8 * cap)):
            shape = CompactShape(bits, cap)
            assert fast.support_positions(shape) == slow.support_positions(shape)
            counts["support_exhaustive"] += 1
            assert fast.apply_gravity(shape) == slow.apply_gravity(shape)
            counts["gravity_exhaustive"] += 1
    _progress("exhaustive support/gravity complete", started)
    gc.collect()

    for bits in range(1 << 16):
        shape = CompactShape(bits, 2)
        assert fast.rotate(shape, 1) == slow.rotate(shape, 1)
        assert fast.rotate(shape, 2) == slow.rotate(shape, 2)
        assert fast.mirror(shape) == slow.mirror(shape)
        assert fast.crystal_generator(shape) == slow.crystal_generator(shape)
        assert fast.pin_push(shape) == slow.pin_push(shape)
        assert fast.cut(shape, 0) == slow.cut(shape, 0)
        assert fast.cut(shape, 1) == slow.cut(shape, 1)
        counts["unary_exhaustive"] += 1
    _progress("exhaustive unary operations complete", started)
    gc.collect()

    rng = random.Random(seed)
    for _ in range(medium_cases):
        cap = rng.randint(1, 12)
        a = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
        b = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
        assert fast.stack(a, b) == slow.stack(a, b)
        assert fast.swap(a, b, 0) == slow.swap(a, b, 0)
        assert fast.swap(a, b, 1) == slow.swap(a, b, 1)
        counts["binary_medium_differential"] += 1
        assert fast.stack_compact_equivalent(a, b) == fast.stack(a, b)
        counts["stack_compact_equivalence"] += 1
    _progress("medium-cap binary differential complete", started)

    for _ in range(large_differential_cases):
        cap = rng.randint(13, 40)
        a = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
        b = fast.apply_gravity(CompactShape(rng.randrange(1 << (8 * cap)), cap))
        assert fast.stack(a, b) == slow.stack(a, b)
        assert fast.swap(a, b, 0) == slow.swap(a, b, 0)
        assert fast.swap(a, b, 1) == slow.swap(a, b, 1)
        counts["binary_large_differential"] += 1
        assert fast.stack_compact_equivalent(a, b) == fast.stack(a, b)
        counts["stack_compact_equivalence"] += 1
    _progress("large-cap binary differential complete", started)

    for _ in range(high_property_cases):
        cap = rng.randint(41, 512)
        raw_a = CompactShape(rng.randrange(1 << (8 * cap)), cap)
        raw_b = CompactShape(rng.randrange(1 << (8 * cap)), cap)
        a = fast.apply_gravity(raw_a)
        b = fast.apply_gravity(raw_b)
        assert fast.apply_gravity(a) == a
        assert fast.apply_gravity(b) == b
        assert fast.rotate(a, 4) == a
        assert fast.mirror(fast.mirror(a)) == a
        assert fast.apply_gravity(fast.pin_push(a)) == fast.pin_push(a)
        assert fast.stack_compact_equivalent(a, b) == fast.stack(a, b)
        counts["high_cap_properties"] += 1
        counts["stack_compact_equivalence"] += 1
    _progress("high-cap properties complete", started)

    return {
        "status": "PASS",
        "seed": seed,
        "parameters": {
            "medium_cases": medium_cases,
            "large_differential_cases": large_differential_cases,
            "high_property_cases": high_property_cases,
        },
        "counts": counts,
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--medium-cases", type=int, default=10_000)
    parser.add_argument("--large-differential-cases", type=int, default=500)
    parser.add_argument("--high-property-cases", type=int, default=2_000)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(
        medium_cases=args.medium_cases,
        large_differential_cases=args.large_differential_cases,
        high_property_cases=args.high_property_cases,
        seed=args.seed,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
