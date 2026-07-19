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


def _coverage_bucket(predecessor: str, target: str, layers: int) -> str:
    subtype = sfa.pp_subtype_candidate(predecessor, layers).subtype
    if subtype == "top_single_c_zero_stack_unresolved_pp_candidate":
        return "zero_stack_half_pair_ngram_candidate"
    if subtype == "mid_stack_delta_pp_candidate":
        base = sfa.mid_stack_delta_base(predecessor)
        if base and sfa.bitmask_push_pin(predecessor, layers) == target:
            return "mid_stack_delta_preimage_candidate"
    if subtype == "direct_pp_candidate":
        witness = sfa.pp_minimal_witness(predecessor, layers)
        if witness.push_matches_target and sfa.bitmask_push_pin(predecessor, layers) == target:
            return "direct_pp_preimage_candidate"
    if subtype in sfa.REFERENCE_DERIVED_PP_POSITIVE_SUBTYPES and sfa.bitmask_push_pin(predecessor, layers) == target:
        return f"{subtype}_preimage_candidate"
    return f"uncovered_{subtype}"


def report(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = replay_ok = 0
    subtype_counts: Counter[str] = Counter()
    coverage_counts: Counter[str] = Counter()
    swap_counts: Counter[str] = Counter()
    stack_counts: Counter[str] = Counter()
    top_counts: Counter[str] = Counter()
    samples: list[str] = []

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
            if len(samples) < args.max_samples:
                samples.append(f"{target}\tmissing_predecessor")
            continue
        if sfa.bitmask_push_pin(predecessor, args.layers) == target:
            replay_ok += 1
        else:
            if len(samples) < args.max_samples:
                samples.append(f"{target}\tpred={predecessor}\treplay_mismatch")
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype
        subtype_counts[subtype] += 1
        coverage_counts[_coverage_bucket(predecessor, target, args.layers)] += 1
        swap_counts[sfa.bitmask_swap_impossibility(predecessor) or "swappable"] += 1
        stack_counts[str(bool(sfa.bitmask_stackability_witnesses(predecessor)))] += 1
        top_counts[predecessor.split(":")[-1]] += 1

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"replay_ok={replay_ok}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    for title, counter in (
        ("subtype_counts", subtype_counts),
        ("coverage_counts", coverage_counts),
        ("predecessor_swap_counts", swap_counts),
        ("predecessor_stackability_counts", stack_counts),
        ("predecessor_top_counts", top_counts),
    ):
        print(f"{title}:")
        for key, count in counter.most_common(args.top):
            print(f"  {key}: {count}")
    if samples:
        print("samples:")
        for sample in samples:
            print(sample)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Report claw preimage family coverage without treating legacy as final logic.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--max-samples", type=int, default=5)
    return report(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
