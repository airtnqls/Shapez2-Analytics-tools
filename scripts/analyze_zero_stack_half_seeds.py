from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import symbolic_frontier_automaton as sfa
from reference_compare import _equiv_half_min, _shape_bits


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def _mask_shape(code: str, keep_mask: int) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return ""
    return sfa.normalize_code(
        ":".join(
            "".join(ch if keep_mask & (1 << q) else "-" for q, ch in enumerate(layer))
            for layer in normalized.split(":")
        )
    )


def _half_key(code: str, layers: int) -> int:
    return _equiv_half_min(_shape_bits(code, layers), layers)


def _half_pair_keys(code: str, layers: int, angle: int) -> tuple[int, int]:
    rotated = code
    for _ in range(angle):
        rotated = sfa.bitmask_rotate_clockwise(rotated)
    left = _mask_shape(rotated, 0b0011)
    right = _mask_shape(rotated, 0b1100)
    return _half_key(left, layers), _half_key(sfa.bitmask_rotate_clockwise(sfa.bitmask_rotate_clockwise(right)), layers)


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = selected = 0
    pair_counts: Counter[tuple[int, int]] = Counter()
    angle_pair_counts: Counter[tuple[int, int, int]] = Counter()
    left_counts: Counter[int] = Counter()
    right_counts: Counter[int] = Counter()
    swap_counts: Counter[str] = Counter()
    stack_counts: Counter[str] = Counter()
    pair_examples: defaultdict[tuple[int, int], list[str]] = defaultdict(list)

    for code in sfa.iter_data_codes(args.data, max_layers=args.layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, args.layers) != target:
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        selected += 1
        swap_counts[sfa.bitmask_swap_impossibility(predecessor) or "swappable"] += 1
        stack_counts[str(bool(sfa.bitmask_stackability_witnesses(predecessor)))] += 1
        for angle in range(2):
            pair = _half_pair_keys(predecessor, args.layers, angle)
            canonical_pair = tuple(sorted(pair))
            pair_counts[canonical_pair] += 1
            angle_pair_counts[(angle, canonical_pair[0], canonical_pair[1])] += 1
            left_counts[pair[0]] += 1
            right_counts[pair[1]] += 1
            if len(pair_examples[canonical_pair]) < args.max_examples:
                pair_examples[canonical_pair].append(f"T={target}\tA={predecessor}\tangle={angle}")

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"selected_zero_stack={selected}")
    print(f"unique_half_pairs={len(pair_counts)}")
    print(f"unique_angle_half_pairs={len(angle_pair_counts)}")
    print(f"unique_left_halves={len(left_counts)}")
    print(f"unique_right_halves={len(right_counts)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    for title, counter in (
        ("swap_counts", swap_counts),
        ("stack_counts", stack_counts),
        ("pair_counts", pair_counts),
        ("angle_pair_counts", angle_pair_counts),
        ("left_counts", left_counts),
        ("right_counts", right_counts),
    ):
        print(f"{title}:")
        for key, count in counter.most_common(args.top):
            print(f"  {key}: {count}")
    if pair_examples:
        print("pair_examples:")
        for pair, rows in list(pair_examples.items())[: args.top]:
            print(f"  {pair}:")
            for row in rows:
                print(f"    {row}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze half-pair seeds for zero-stack claw PP predecessors.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--max-examples", type=int, default=2)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
