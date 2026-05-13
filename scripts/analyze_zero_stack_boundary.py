from __future__ import annotations

import argparse
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
from analyze_claw_preimages import _claw_predecessor


def _root_key(code: str) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return "empty"
    tree = sfa.reference_decomposition_tree(normalized, len(normalized.split(":")))
    if tree is None:
        return "none"
    return sfa.decomposition_tree_root_key(tree)


def _collect_predecessors(args: argparse.Namespace) -> tuple[list[str], float]:
    started = time.perf_counter()
    predecessors: list[str] = []
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
        predecessors.append(predecessor)
    return predecessors, time.perf_counter() - started


def _analyze_width(predecessors: list[str], width: int, args: argparse.Namespace, started: float) -> None:
    known = set(predecessors)
    lowers_by_top: defaultdict[str, set[str]] = defaultdict(set)
    suffixes_by_first: defaultdict[str, set[str]] = defaultdict(set)
    suffixes_by_boundary: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    suffixes_by_root_boundary: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)
    lower_root_by_lower: dict[str, str] = {}

    boundary_counts: Counter[tuple[str, str]] = Counter()
    root_boundary_counts: Counter[tuple[str, str, str]] = Counter()
    root_counts: Counter[str] = Counter()
    lower_top_counts: Counter[str] = Counter()
    suffix_first_counts: Counter[str] = Counter()

    for predecessor in predecessors:
        parts = predecessor.split(":")
        if len(parts) <= width:
            continue
        lower = sfa.normalize_code(":".join(parts[:-width]))
        suffix_parts = parts[-width:]
        suffix = ":".join(suffix_parts)
        lower_top = lower.split(":")[-1] if lower else "empty"
        suffix_first = suffix_parts[0]
        root = lower_root_by_lower.get(lower)
        if root is None:
            root = _root_key(lower)
            lower_root_by_lower[lower] = root

        lowers_by_top[lower_top].add(lower)
        suffixes_by_first[suffix_first].add(suffix)
        suffixes_by_boundary[(lower_top, suffix_first)].add(suffix)
        suffixes_by_root_boundary[(root, lower_top, suffix_first)].add(suffix)
        boundary_counts[(lower_top, suffix_first)] += 1
        root_boundary_counts[(root, lower_top, suffix_first)] += 1
        root_counts[root] += 1
        lower_top_counts[lower_top] += 1
        suffix_first_counts[suffix_first] += 1

    boundary_candidates: set[str] = set()
    root_boundary_candidates: set[str] = set()
    boundary_truncated = False
    root_boundary_truncated = False

    for (lower_top, suffix_first), suffixes in suffixes_by_boundary.items():
        for lower in lowers_by_top[lower_top]:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                boundary_truncated = True
                break
            for suffix in suffixes:
                boundary_candidates.add(f"{lower}:{suffix}" if lower else suffix)
        if boundary_truncated:
            break

    lowers_by_root_top: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    for lower, root in lower_root_by_lower.items():
        lower_top = lower.split(":")[-1] if lower else "empty"
        lowers_by_root_top[(root, lower_top)].add(lower)

    if not boundary_truncated:
        for (root, lower_top, suffix_first), suffixes in suffixes_by_root_boundary.items():
            for lower in lowers_by_root_top[(root, lower_top)]:
                if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                    root_boundary_truncated = True
                    break
                for suffix in suffixes:
                    root_boundary_candidates.add(f"{lower}:{suffix}" if lower else suffix)
            if root_boundary_truncated:
                break

    boundary_overlap = boundary_candidates & known
    root_boundary_overlap = root_boundary_candidates & known

    print(f"width={width}")
    print(f"  known_predecessors={len(known)}")
    print(f"  unique_lowers={len(lower_root_by_lower)}")
    print(f"  unique_lower_tops={len(lowers_by_top)}")
    print(f"  unique_suffix_first_layers={len(suffixes_by_first)}")
    print(f"  unique_boundary_pairs={len(boundary_counts)}")
    print(f"  unique_root_boundary_pairs={len(root_boundary_counts)}")
    print(f"  boundary_candidates={len(boundary_candidates)}")
    print(f"  boundary_overlap={len(boundary_overlap)}")
    print(f"  boundary_extra={len(boundary_candidates - known)}")
    print(f"  boundary_recall={100.0 * len(boundary_overlap) / len(known) if known else 100:.6f}%")
    print(f"  boundary_truncated={boundary_truncated}")
    print(f"  root_boundary_candidates={len(root_boundary_candidates)}")
    print(f"  root_boundary_overlap={len(root_boundary_overlap)}")
    print(f"  root_boundary_extra={len(root_boundary_candidates - known)}")
    print(f"  root_boundary_recall={100.0 * len(root_boundary_overlap) / len(known) if known else 100:.6f}%")
    print(f"  root_boundary_truncated={root_boundary_truncated}")

    sections = (
        ("root_counts", root_counts),
        ("lower_top_counts", lower_top_counts),
        ("suffix_first_counts", suffix_first_counts),
        ("boundary_counts", boundary_counts),
        ("root_boundary_counts", root_boundary_counts),
    )
    for title, counter in sections:
        print(f"  {title}:")
        for key, count in counter.most_common(args.top):
            print(f"    {key}: {count}")


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    predecessors, collect_elapsed = _collect_predecessors(args)
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"selected_zero_stack_predecessors={len(predecessors)}")
    print(f"collect_elapsed={collect_elapsed:.6f}s")
    for width in args.width:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            print("stopped=max_seconds")
            break
        _analyze_width(predecessors, width, args, started)
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure lower/suffix boundary constraints for zero-stack claw preimages.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--width", type=int, action="append", default=[2, 3, 4])
    parser.add_argument("--top", type=int, default=16)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
