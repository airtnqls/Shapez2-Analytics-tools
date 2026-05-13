from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import sys
import time
from collections import Counter, deque
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


def _trace_seed(code: str, layers: int, allow_terminal_crystal: bool) -> str | None:
    current = sfa.normalize_code(code)
    seen: set[str] = set()
    while current and current not in seen and sfa.top_single_c_zero_stack_candidate(current):
        seen.add(current)
        parts = current.split(":")
        current = sfa.normalize_code(":".join(parts[1:]))
    if not current:
        return None
    witness = sfa.zero_stack_trace_seed(code, layers, allow_terminal_crystal=allow_terminal_crystal)
    if witness is None:
        return None
    return current


def _known(args: argparse.Namespace) -> tuple[set[str], set[str], set[str]]:
    predecessors: set[str] = set()
    targets: set[str] = set()
    seeds: set[str] = set()
    started = time.perf_counter()
    total = 0
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
        if sfa.bitmask_push_pin(predecessor, args.layers) != target:
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        seed = _trace_seed(predecessor, args.layers, args.allow_terminal_crystal)
        if seed is None:
            continue
        predecessors.add(predecessor)
        targets.add(target)
        seeds.add(seed)
    return predecessors, targets, seeds


def _all_layers(alphabet: str) -> tuple[str, ...]:
    return tuple("".join(chars) for chars in itertools.product(alphabet, repeat=4))


def _candidate_allowed(code: str, args: argparse.Namespace) -> bool:
    if not sfa.top_single_c_zero_stack_candidate(code):
        return False
    if sfa.zero_stack_trace_seed(code, args.layers, allow_terminal_crystal=args.allow_terminal_crystal) is None:
        return False
    if args.prune_swappable and sfa.bitmask_swap_impossibility(code) is not None:
        return False
    return True


def _record_allowed(code: str, args: argparse.Namespace) -> bool:
    if args.require_swappable and sfa.bitmask_swap_impossibility(code) is not None:
        return False
    if args.require_corner and not sfa.corner_columns_allowed(code):
        return False
    if args.reject_processed_claw and sfa.processed_claw_fast_reject_reason(code) is not None:
        return False
    return True


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    known_predecessors, known_targets, seeds = _known(args)
    layers = _all_layers(args.alphabet)
    queue = deque(sorted(seeds))
    seen = set(seeds)
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    depth_counts: Counter[int] = Counter()
    rejected = Counter()
    expanded = 0

    while queue:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        current = queue.popleft()
        current_depth = len(current.split(":")) if current else 0
        if current_depth >= args.layers:
            continue
        for layer in layers:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                break
            if args.max_expansions and expanded >= args.max_expansions:
                break
            expanded += 1
            candidate = sfa.normalize_code(f"{layer}:{current}" if current else layer)
            if not candidate or candidate in seen:
                rejected["duplicate_or_empty"] += 1
                continue
            if len(candidate.split(":")) > args.layers:
                rejected["too_tall"] += 1
                continue
            if not _candidate_allowed(candidate, args):
                rejected["predicate"] += 1
                continue
            seen.add(candidate)
            queue.append(candidate)
            depth_counts[len(candidate.split(":"))] += 1
            if (not args.record_full_height_only or len(candidate.split(":")) == args.layers) and _record_allowed(candidate, args):
                generated_predecessors.add(candidate)
                pushed = sfa.bitmask_push_pin(candidate, args.layers)
                if pushed:
                    generated_targets.add(pushed)
        if args.max_expansions and expanded >= args.max_expansions:
            break

    predecessor_overlap = generated_predecessors & known_predecessors
    target_overlap = generated_targets & known_targets
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"known_zero_stack_predecessors={len(known_predecessors)}")
    print(f"known_zero_stack_targets={len(known_targets)}")
    print(f"seeds={len(seeds)}")
    print(f"expanded={expanded}")
    print(f"seen={len(seen)}")
    print(f"generated_predecessors={len(generated_predecessors)}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"predecessor_overlap={len(predecessor_overlap)}")
    print(f"predecessor_recall={100.0 * len(predecessor_overlap) / len(known_predecessors) if known_predecessors else 100:.6f}%")
    print(f"predecessor_extra={len(generated_predecessors - known_predecessors)}")
    print(f"target_overlap={len(target_overlap)}")
    print(f"target_recall={100.0 * len(target_overlap) / len(known_targets) if known_targets else 100:.6f}%")
    print(f"target_extra={len(generated_targets - known_targets)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("depth_counts:")
    for key, count in sorted(depth_counts.items()):
        print(f"  {key}: {count}")
    print("rejected:")
    for key, count in rejected.most_common():
        print(f"  {key}: {count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate zero-stack claw PP predecessors by reversing bottom-drop trace.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-expansions", type=int, default=0)
    parser.add_argument("--alphabet", default="-SPc")
    parser.add_argument("--allow-terminal-crystal", action="store_true")
    parser.add_argument("--require-swappable", action="store_true")
    parser.add_argument("--require-corner", action="store_true")
    parser.add_argument("--reject-processed-claw", action="store_true")
    parser.add_argument("--prune-swappable", action="store_true")
    parser.add_argument("--record-full-height-only", action="store_true")
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
