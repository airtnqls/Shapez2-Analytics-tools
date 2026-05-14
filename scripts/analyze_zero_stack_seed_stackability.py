from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import symbolic_frontier_automaton as sfa


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit zero-stack claw predecessors by their terminal seed stackability."
    )
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--examples", type=int, default=8)
    args = parser.parse_args()

    started = time.perf_counter()
    total = 0
    replay_ok = 0
    zero_stack = 0
    seed_found = 0
    seed_stackable = 0
    subtype_counts = Counter()
    seed_layers = Counter()
    seed_current_top = Counter()
    seed_base_top = Counter()
    witness_delta = Counter()
    witness_heights = Counter()
    misses: list[str] = []

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
        if predecessor and sfa.bitmask_push_pin(predecessor, args.layers) == target:
            replay_ok += 1
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype if predecessor else "none"
        subtype_counts[subtype] += 1
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        zero_stack += 1
        seed = sfa.zero_stack_trace_seed(predecessor, args.layers, allow_terminal_crystal=True)
        if seed is None:
            if len(misses) < args.examples:
                misses.append(f"missing_seed\tT={target}\tA={predecessor}")
            continue
        seed_found += 1
        current, base = seed
        current_parts = current.split(":") if current else []
        base_parts = base.split(":") if base else []
        seed_layers[len(current_parts)] += 1
        seed_current_top[current_parts[-1] if current_parts else ""] += 1
        seed_base_top[base_parts[-1] if base_parts else ""] += 1
        witnesses = sfa.bitmask_stackability_witnesses(current)
        if not witnesses:
            if len(misses) < args.examples:
                misses.append(f"not_stackable_seed\tT={target}\tA={predecessor}\tseed={current}\tbase={base}")
            continue
        seed_stackable += 1
        first = witnesses[0]
        witness_delta[first.stacked_delta] += 1
        witness_heights[first.heights] += 1

    elapsed = time.perf_counter() - started
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"replay_ok={replay_ok}")
    print(f"zero_stack={zero_stack}")
    print(f"seed_found={seed_found}")
    print(f"seed_stackable={seed_stackable}")
    print(f"elapsed={elapsed:.6f}s")
    print("subtypes:")
    for key, count in subtype_counts.most_common(args.top):
        print(f"  {key}: {count}")
    print("seed_layers:")
    for key, count in seed_layers.most_common(args.top):
        print(f"  {key}: {count}")
    print("seed_current_top:")
    for key, count in seed_current_top.most_common(args.top):
        print(f"  {key}: {count}")
    print("seed_base_top:")
    for key, count in seed_base_top.most_common(args.top):
        print(f"  {key}: {count}")
    print("witness_delta:")
    for key, count in witness_delta.most_common(args.top):
        print(f"  {key}: {count}")
    print("witness_heights:")
    for key, count in witness_heights.most_common(args.top):
        print(f"  {key}: {count}")
    if misses:
        print("miss_examples:")
        for item in misses:
            print(f"  {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
