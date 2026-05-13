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


def _cells(code: str) -> set[tuple[int, int, str]]:
    out: set[tuple[int, int, str]] = set()
    for l, layer in enumerate(sfa.normalize_code(code).split(":")):
        for q, ch in enumerate(layer):
            if ch != "-":
                out.add((l, q, ch))
    return out


def _column_heights(code: str) -> tuple[int, int, int, int]:
    parts = sfa.normalize_code(code).split(":") if code else []
    heights: list[int] = []
    for q in range(4):
        height = 0
        for l, layer in enumerate(parts):
            if layer[q] != "-":
                height = l + 1
        heights.append(height)
    return tuple(heights)  # type: ignore[return-value]


def _top_c_signature(code: str) -> str:
    parts = sfa.normalize_code(code).split(":") if code else []
    for l in range(len(parts) - 1, -1, -1):
        count = parts[l].count("c")
        if count:
            return f"L{l}:c{count}:{parts[l]}"
    return "no_c"


def _top_pair(code: str) -> str:
    parts = sfa.normalize_code(code).split(":") if code else []
    if not parts:
        return "empty"
    prev = parts[-2] if len(parts) >= 2 else "none"
    return f"{prev}>{parts[-1]}"


def _remove_highest_single_c(code: str) -> str:
    parts = [list(layer) for layer in sfa.normalize_code(code).split(":") if layer]
    for l in range(len(parts) - 1, -1, -1):
        c_positions = [q for q, ch in enumerate(parts[l]) if ch == "c"]
        if c_positions:
            if len(c_positions) != 1:
                return ""
            parts[l][c_positions[0]] = "-"
            return sfa.normalize_code(":".join("".join(layer) for layer in parts))
    return ""


def _bucket(value: int, cap: int = 10) -> str:
    return f">{cap}" if value > cap else str(value)


def _minimal_drop(code: str) -> str:
    parts = sfa.normalize_code(code).split(":") if code else []
    return sfa.normalize_code(":".join(parts[1:]))


def _zero_stack_trace(code: str, layers: int, max_depth: int) -> tuple[int, str, int, str, str]:
    current = sfa.normalize_code(code)
    depth = 0
    seen: set[str] = set()
    while current and current not in seen and depth < max_depth and sfa.top_single_c_zero_stack_candidate(current):
        seen.add(current)
        depth += 1
        current = _minimal_drop(current)
    if not current:
        return depth, "empty", 0, "empty", ""
    subtype = sfa.pp_subtype_candidate(current, layers).subtype
    stack_count = len(sfa.bitmask_stackability_witnesses(current))
    return depth, subtype, stack_count, _top_pair(current), current


def _min_stack_delta(pred: str) -> tuple[str, str, str]:
    witnesses = sfa.bitmask_stackability_witnesses(pred)
    if not witnesses:
        return "none", "none", "none"
    pred_cells = _cells(pred)
    best_delta = None
    best_swap = "none"
    best_heights = "none"
    for witness in witnesses:
        delta = len(pred_cells - _cells(witness.base))
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_swap = sfa.bitmask_swap_impossibility(witness.base) or "swappable"
            best_heights = ",".join(str(v) for v in witness.heights)
    return str(best_delta), best_swap, best_heights


def _inverse_summary(target: str, pred: str, layers: int) -> tuple[str, str]:
    groups = (
        ("simple", sfa.bitmask_inverse_push_pin_candidates(target, layers)),
        ("bridge", sfa.bitmask_bridge_inverse_push_pin_candidates(target, layers)),
        ("connected", sfa.bitmask_connected_shatter_inverse_push_pin_candidates(target, layers)),
        ("piece_lift", sfa.bitmask_piece_lift_shatter_inverse_push_pin_candidates(target, layers)),
        ("double_s", sfa.bitmask_double_s_lift_shatter_inverse_push_pin_candidates(target, layers)),
    )
    counts = ",".join(f"{name}:{len(candidates)}" for name, candidates in groups)
    contains = ",".join(name for name, candidates in groups if pred in candidates) or "none"
    return counts, contains


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = processed = selected = push_ok = 0
    subtype_counts: Counter[str] = Counter()
    pred_swap_counts: Counter[str] = Counter()
    pred_layers_counts: Counter[int] = Counter()
    pred_c_counts: Counter[int] = Counter()
    pred_top_c_counts: Counter[str] = Counter()
    pred_top_pair_counts: Counter[str] = Counter()
    pred_column_heights: Counter[tuple[int, int, int, int]] = Counter()
    stack_witness_counts: Counter[str] = Counter()
    min_stack_delta_counts: Counter[str] = Counter()
    min_stack_base_swap_counts: Counter[str] = Counter()
    min_stack_heights_counts: Counter[str] = Counter()
    top_removed_subtype_counts: Counter[str] = Counter()
    top_removed_stack_counts: Counter[str] = Counter()
    top_removed_swap_counts: Counter[str] = Counter()
    top_removed_push_counts: Counter[str] = Counter()
    minimal_pred_subtype_counts: Counter[str] = Counter()
    minimal_pred_stack_counts: Counter[str] = Counter()
    minimal_pred_swap_counts: Counter[str] = Counter()
    zero_stack_trace_depth_counts: Counter[int] = Counter()
    zero_stack_trace_exit_counts: Counter[str] = Counter()
    zero_stack_trace_exit_stack_counts: Counter[str] = Counter()
    zero_stack_trace_exit_top_pair_counts: Counter[str] = Counter()
    zero_stack_trace_exit_safe_stack_counts: Counter[str] = Counter()
    zero_stack_trace_exit_min_base_swap_counts: Counter[str] = Counter()
    zero_stack_trace_seed_counts: Counter[str] = Counter()
    inverse_count_counts: Counter[str] = Counter()
    inverse_contains_counts: Counter[str] = Counter()
    target_top_pair_counts: Counter[str] = Counter()
    target_removal_counts: Counter[str] = Counter()
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
        pred = _claw_predecessor(target)
        if not pred:
            continue
        processed += 1
        if sfa.bitmask_push_pin(pred, max(args.layers, len(target.split(":")))) == target:
            push_ok += 1
        subtype = sfa.pp_subtype_candidate(pred, args.layers).subtype
        subtype_counts[subtype] += 1
        unresolved_subtypes = {
            "unclassified_pp_candidate",
            "top_single_c_zero_stack_unresolved_pp_candidate",
        }
        if not args.all_subtypes and subtype not in unresolved_subtypes:
            continue
        selected += 1

        pred_parts = pred.split(":")
        pred_layers_counts[len(pred_parts)] += 1
        pred_c_counts[sum(layer.count("c") for layer in pred_parts)] += 1
        pred_top_c_counts[_top_c_signature(pred)] += 1
        pred_top_pair_counts[_top_pair(pred)] += 1
        pred_column_heights[_column_heights(pred)] += 1
        pred_swap_counts[sfa.bitmask_swap_impossibility(pred) or "swappable"] += 1

        witnesses = sfa.bitmask_stackability_witnesses(pred)
        stack_witness_counts[_bucket(len(witnesses))] += 1
        min_delta, min_swap, min_heights = _min_stack_delta(pred)
        min_stack_delta_counts[min_delta] += 1
        min_stack_base_swap_counts[min_swap] += 1
        min_stack_heights_counts[min_heights] += 1

        top_removed = _remove_highest_single_c(pred)
        if top_removed:
            top_removed_subtype_counts[sfa.pp_subtype_candidate(top_removed, args.layers).subtype] += 1
            top_removed_stack_counts[_bucket(len(sfa.bitmask_stackability_witnesses(top_removed)))] += 1
            top_removed_swap_counts[sfa.bitmask_swap_impossibility(top_removed) or "swappable"] += 1
            top_removed_push_counts[str(sfa.bitmask_push_pin(top_removed, args.layers) == pred)] += 1
        else:
            top_removed_subtype_counts["none"] += 1

        minimal_pred = sfa.pp_minimal_witness(pred, args.layers).predecessor
        if minimal_pred:
            minimal_pred_subtype_counts[sfa.pp_subtype_candidate(minimal_pred, args.layers).subtype] += 1
            minimal_pred_stack_counts[_bucket(len(sfa.bitmask_stackability_witnesses(minimal_pred)))] += 1
            minimal_pred_swap_counts[sfa.bitmask_swap_impossibility(minimal_pred) or "swappable"] += 1
        else:
            minimal_pred_subtype_counts["empty"] += 1

        trace_depth, trace_exit, trace_exit_stack, trace_exit_top, trace_exit_code = _zero_stack_trace(
            pred, args.layers, args.trace_depth
        )
        zero_stack_trace_depth_counts[trace_depth] += 1
        zero_stack_trace_exit_counts[trace_exit] += 1
        zero_stack_trace_exit_stack_counts[_bucket(trace_exit_stack)] += 1
        zero_stack_trace_exit_top_pair_counts[trace_exit_top] += 1
        if trace_exit_code:
            zero_stack_trace_exit_safe_stack_counts[str(sfa.safe_stackability_witness(trace_exit_code) is not None)] += 1
            _delta, exit_min_swap, _heights = _min_stack_delta(trace_exit_code)
            zero_stack_trace_exit_min_base_swap_counts[exit_min_swap] += 1
        zero_stack_trace_seed_counts[str(sfa.zero_stack_trace_seed(pred, args.layers) is not None)] += 1

        inv_contains = "skipped"
        if not args.skip_inverse:
            inv_counts, inv_contains = _inverse_summary(target, pred, args.layers)
            inverse_count_counts[inv_counts] += 1
            inverse_contains_counts[inv_contains] += 1

        target_top_pair_counts[_top_pair(target)] += 1
        target_removal_counts[str(sfa.bitmask_layer_removal_context(target)[:3])] += 1
        if len(examples[subtype]) < args.max_examples:
            examples[subtype].append(f"T={target}\tA={pred}\tstack={len(witnesses)}\tmin_delta={min_delta}\tinv_contains={inv_contains}")

    elapsed = time.perf_counter() - started
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"processed={processed}")
    print(f"push_ok={push_ok}")
    print(f"selected={selected}")
    print(f"elapsed={elapsed:.6f}s")
    print("subtype_counts:")
    for key, count in subtype_counts.most_common(20):
        print(f"  {key}: {count}")
    sections = (
        ("pred_swap_counts", pred_swap_counts),
        ("pred_layers_counts", pred_layers_counts),
        ("pred_c_counts", pred_c_counts),
        ("pred_top_c_counts", pred_top_c_counts),
        ("pred_top_pair_counts", pred_top_pair_counts),
        ("pred_column_heights", pred_column_heights),
        ("stack_witness_counts", stack_witness_counts),
        ("min_stack_delta_counts", min_stack_delta_counts),
        ("min_stack_base_swap_counts", min_stack_base_swap_counts),
        ("min_stack_heights_counts", min_stack_heights_counts),
        ("top_removed_subtype_counts", top_removed_subtype_counts),
        ("top_removed_stack_counts", top_removed_stack_counts),
        ("top_removed_swap_counts", top_removed_swap_counts),
        ("top_removed_push_counts", top_removed_push_counts),
        ("minimal_pred_subtype_counts", minimal_pred_subtype_counts),
        ("minimal_pred_stack_counts", minimal_pred_stack_counts),
        ("minimal_pred_swap_counts", minimal_pred_swap_counts),
        ("zero_stack_trace_depth_counts", zero_stack_trace_depth_counts),
        ("zero_stack_trace_exit_counts", zero_stack_trace_exit_counts),
        ("zero_stack_trace_exit_stack_counts", zero_stack_trace_exit_stack_counts),
        ("zero_stack_trace_exit_top_pair_counts", zero_stack_trace_exit_top_pair_counts),
        ("zero_stack_trace_exit_safe_stack_counts", zero_stack_trace_exit_safe_stack_counts),
        ("zero_stack_trace_exit_min_base_swap_counts", zero_stack_trace_exit_min_base_swap_counts),
        ("zero_stack_trace_seed_counts", zero_stack_trace_seed_counts),
        ("inverse_count_counts", inverse_count_counts),
        ("inverse_contains_counts", inverse_contains_counts),
        ("target_top_pair_counts", target_top_pair_counts),
        ("target_removal_counts", target_removal_counts),
    )
    for title, counter in sections:
        print(f"{title}:")
        for key, count in counter.most_common(args.top):
            print(f"  {key}: {count}")
    if examples:
        print("examples:")
        for subtype, rows in examples.items():
            print(f"  {subtype}:")
            for row in rows:
                print(f"    {row}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze PP-unclassified claw predecessors.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--all-subtypes", action="store_true")
    parser.add_argument("--skip-inverse", action="store_true")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--max-examples", type=int, default=5)
    parser.add_argument("--trace-depth", type=int, default=8)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
