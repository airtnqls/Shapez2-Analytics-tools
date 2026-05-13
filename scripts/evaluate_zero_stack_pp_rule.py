from __future__ import annotations

import argparse
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


def _strict(code: str) -> tuple[str, str, str]:
    _legacy, strict, cls, reason = sfa.legacy_verdict(code)
    return strict, cls, reason


def _top_pair(code: str) -> str:
    parts = sfa.normalize_code(code).split(":") if code else []
    if not parts:
        return "empty"
    prev = parts[-2] if len(parts) >= 2 else "none"
    return f"{prev}>{parts[-1]}"


def _trace_depth(code: str) -> int:
    current = sfa.normalize_code(code)
    seen: set[str] = set()
    depth = 0
    while current and current not in seen and sfa.top_single_c_zero_stack_candidate(current):
        seen.add(current)
        current = sfa.normalize_code(":".join(current.split(":")[1:]))
        depth += 1
    return depth


def _source_contains(target: str, pred: str, layers: int) -> str:
    sources = (
        ("simple", sfa.bitmask_inverse_push_pin_candidates(target, layers)),
        ("bridge", sfa.bitmask_bridge_inverse_push_pin_candidates(target, layers)),
        ("connected", sfa.bitmask_connected_shatter_inverse_push_pin_candidates(target, layers)),
    )
    return ",".join(name for name, candidates in sources if pred in candidates) or "none"


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = hits = strict_known = strict_match = 0
    hit_pairs: Counter[tuple[str, str]] = Counter()
    predecessor_subtypes: Counter[str] = Counter()
    strict_feature_counts: Counter[tuple[str, str, str]] = Counter()
    source_counts: Counter[str] = Counter()
    miss_reasons: Counter[str] = Counter()
    samples: list[str] = []

    if args.random:
        code_iter = sfa.iter_random_codes(args.random, args.layers, args.seed)
    elif args.per_file:
        code_iter = sfa.iter_data_codes_by_file(args.data, args.per_file, args.seed, not args.no_shuffle, args.layers)
    else:
        code_iter = sfa.iter_data_codes(args.data, args.layers)

    for code in code_iter:
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        normalized = sfa.normalize_code(code)
        if not normalized:
            continue
        total += 1
        pred = sfa.zero_stack_pp_predecessor_witness(normalized, args.layers, include_connected=args.include_connected)
        if pred is None:
            miss_reasons["no_zero_stack_pp_predecessor"] += 1
            continue
        hits += 1
        source_counts[_source_contains(normalized, pred, args.layers)] += 1
        predecessor_subtypes[sfa.pp_subtype_candidate(pred, args.layers).subtype] += 1
        strict, cls, reason = _strict(normalized)
        hit_pairs[(strict, reason or cls)] += 1
        strict_group = "positive" if strict == "possible" else "negative" if strict == "impossible" else "unknown"
        strict_feature_counts[(strict_group, "target_top", _top_pair(normalized))] += 1
        strict_feature_counts[(strict_group, "target_removal", str(sfa.bitmask_layer_removal_context(normalized)[:3]))] += 1
        strict_feature_counts[(strict_group, "pred_top", _top_pair(pred))] += 1
        strict_feature_counts[(strict_group, "pred_swap", sfa.bitmask_swap_impossibility(pred) or "swappable")] += 1
        strict_feature_counts[(strict_group, "trace_depth", str(_trace_depth(pred)))] += 1
        if strict != "unknown":
            strict_known += 1
            if strict == "possible":
                strict_match += 1
            elif len(samples) < args.max_samples:
                samples.append(f"{normalized}\tpred={pred}\tstrict={strict}\tlegacy={cls}\treason={reason}")

    elapsed = time.perf_counter() - started
    print(f"input={args.data if not args.random else 'random'}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"hits={hits}")
    print(f"hit_rate={100.0 * hits / total if total else 0:.6f}%")
    print(f"strict_known={strict_known}")
    print(f"strict_possible_hits={strict_match}")
    print(f"strict_possible_precision={100.0 * strict_match / strict_known if strict_known else 100:.6f}%")
    print(f"elapsed={elapsed:.6f}s")
    print("predecessor_subtypes:")
    for key, count in predecessor_subtypes.most_common(args.top):
        print(f"  {key}: {count}")
    print("source_counts:")
    for key, count in source_counts.most_common(args.top):
        print(f"  {key}: {count}")
    print("hit_strict_pairs:")
    for (strict, reason), count in hit_pairs.most_common(args.top):
        print(f"  {strict}/{reason}: {count}")
    print("strict_features:")
    for (group, name, value), count in strict_feature_counts.most_common(args.top * 3):
        print(f"  {group}/{name}/{value}: {count}")
    print("miss_reasons:")
    for key, count in miss_reasons.most_common(args.top):
        print(f"  {key}: {count}")
    if samples:
        print("negative_samples:")
        for sample in samples:
            print(sample)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the zero-stack PP predecessor candidate rule.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--per-file", type=int, default=0)
    parser.add_argument("--random", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--include-connected", action="store_true")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--max-samples", type=int, default=8)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
