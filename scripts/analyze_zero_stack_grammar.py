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


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def _drop_bottom_trace(code: str, layers: int) -> tuple[tuple[str, ...], str, str]:
    current = sfa.normalize_code(code)
    removed: list[str] = []
    seen: set[str] = set()
    while current and current not in seen and sfa.top_single_c_zero_stack_candidate(current):
        seen.add(current)
        parts = current.split(":")
        removed.append(parts[0])
        current = sfa.normalize_code(":".join(parts[1:]))
    seed_type = "none"
    if sfa.zero_stack_trace_seed(code, layers) is not None:
        seed_type = "stack_seed"
    if sfa.zero_stack_trace_seed(code, layers, allow_terminal_crystal=True) is not None:
        seed_type = "terminal_or_stack_seed"
    return tuple(removed), current, seed_type


def _top_pair(code: str) -> str:
    parts = sfa.normalize_code(code).split(":") if code else []
    if not parts:
        return "empty"
    prev = parts[-2] if len(parts) >= 2 else "none"
    return f"{prev}>{parts[-1]}"


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = selected = push_ok = 0
    seed_type_counts: Counter[str] = Counter()
    depth_counts: Counter[int] = Counter()
    seed_counts: Counter[str] = Counter()
    seed_top_counts: Counter[str] = Counter()
    prefix_counts: Counter[tuple[str, ...]] = Counter()
    prefix_layer_counts: Counter[tuple[int, str]] = Counter()
    transition_counts: Counter[tuple[str, str]] = Counter()
    transition_by_index_counts: Counter[tuple[int, str, str]] = Counter()
    prefix_signature_counts: Counter[str] = Counter()
    target_top_counts: Counter[str] = Counter()
    suffix_counts: Counter[tuple[int, str]] = Counter()
    examples: defaultdict[str, list[str]] = defaultdict(list)

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
        if not predecessor:
            continue
        if sfa.bitmask_push_pin(predecessor, args.layers) == target:
            push_ok += 1
        if sfa.pp_subtype_candidate(predecessor, args.layers).subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        pred_parts = predecessor.split(":")
        for width in range(1, min(args.layers, len(pred_parts)) + 1):
            suffix_counts[(width, ":".join(pred_parts[-width:]))] += 1
        selected += 1
        prefix, seed, seed_type = _drop_bottom_trace(predecessor, args.layers)
        seed_type_counts[seed_type] += 1
        depth_counts[len(prefix)] += 1
        seed_counts[seed] += 1
        seed_top_counts[_top_pair(seed)] += 1
        prefix_counts[prefix] += 1
        prefix_signature_counts["|".join(prefix)] += 1
        for index, layer in enumerate(prefix):
            prefix_layer_counts[(index, layer)] += 1
        chain = list(prefix) + (seed.split(":") if seed else [])
        for index, (lower, upper) in enumerate(zip(chain, chain[1:])):
            transition_counts[(lower, upper)] += 1
            transition_by_index_counts[(index, lower, upper)] += 1
        target_top_counts[_top_pair(target)] += 1
        if len(examples[seed_type]) < args.max_examples:
            examples[seed_type].append(f"T={target}\tA={predecessor}\tprefix={prefix}\tseed={seed}")

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"push_ok={push_ok}")
    print(f"selected_zero_stack={selected}")
    print(f"unique_seeds={len(seed_counts)}")
    print(f"unique_prefixes={len(prefix_counts)}")
    print(f"unique_transitions={len(transition_counts)}")
    for index in range(args.layers):
        unique_transitions_at_index = {
            (lower, upper) for (idx, lower, upper), _count in transition_by_index_counts.items() if idx == index
        }
        if unique_transitions_at_index:
            print(f"unique_transitions_at_{index}={len(unique_transitions_at_index)}")
    for index in range(args.layers):
        unique_at_index = {layer for (idx, layer), _count in prefix_layer_counts.items() if idx == index}
        if unique_at_index:
            print(f"unique_prefix_layers_at_{index}={len(unique_at_index)}")
    for width in range(1, args.layers + 1):
        unique_suffixes = {suffix for (suffix_width, suffix), _count in suffix_counts.items() if suffix_width == width}
        if unique_suffixes:
            print(f"unique_suffixes_width_{width}={len(unique_suffixes)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    sections = (
        ("seed_type_counts", seed_type_counts),
        ("depth_counts", depth_counts),
        ("seed_counts", seed_counts),
        ("seed_top_counts", seed_top_counts),
        ("prefix_signature_counts", prefix_signature_counts),
        ("prefix_layer_counts", prefix_layer_counts),
        ("transition_counts", transition_counts),
        ("transition_by_index_counts", transition_by_index_counts),
        ("suffix_counts", suffix_counts),
        ("target_top_counts", target_top_counts),
    )
    for title, counter in sections:
        print(f"{title}:")
        for key, count in counter.most_common(args.top):
            print(f"  {key}: {count}")
    if examples:
        print("examples:")
        for key, rows in examples.items():
            print(f"  {key}:")
            for row in rows:
                print(f"    {row}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract a prefix grammar from zero-stack claw predecessors.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--top", type=int, default=32)
    parser.add_argument("--max-examples", type=int, default=4)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
