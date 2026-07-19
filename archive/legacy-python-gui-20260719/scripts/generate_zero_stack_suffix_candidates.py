from __future__ import annotations

import argparse
import itertools
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import symbolic_frontier_automaton as sfa
from analyze_claw_preimages import _claw_predecessor

TARGET_TOP_FRONTIER = frozenset(
    {
        "-ScS",
        "S-Sc",
        "cS-S",
        "ScS-",
        "Sc--",
        "--cS",
        "S--c",
        "c--S",
        "--Sc",
        "cS--",
        "-cS-",
        "-Sc-",
        "c---",
        "--c-",
        "-c--",
        "---c",
    }
)


def _all_layers(alphabet: str) -> tuple[str, ...]:
    return tuple("".join(chars) for chars in itertools.product(alphabet, repeat=4))


def _known_zero_stack(args: argparse.Namespace) -> tuple[set[str], set[str]]:
    targets: set[str] = set()
    suffixes: set[str] = set()
    for code in sfa.iter_data_codes(args.data, max_layers=args.layers):
        target = sfa.normalize_code(code)
        if not target:
            continue
        predecessor = _claw_predecessor(target)
        if not predecessor:
            continue
        if sfa.pp_subtype_candidate(predecessor, args.layers).subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        parts = predecessor.split(":")
        if len(parts) >= args.suffix_width:
            suffixes.add(":".join(parts[-args.suffix_width :]))
            targets.add(target)
    return targets, suffixes


def _lower_prefix_allowed(code: str, mode: str) -> bool:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return mode in {
            "none",
            "physics",
            "physics-corner",
            "swappable",
            "stackable",
            "swappable-stackable",
            "decomposition",
        }
    if mode == "none":
        return True
    if mode in {"physics", "physics-corner", "swappable", "stackable", "swappable-stackable"}:
        if not sfa.bitmask_physics_stable(normalized):
            return False
    if mode in {"physics-corner", "swappable", "stackable", "swappable-stackable"}:
        if not sfa.corner_columns_allowed(normalized):
            return False
    if mode in {"swappable", "swappable-stackable"}:
        if sfa.bitmask_swap_impossibility(normalized) is not None:
            return False
    if mode in {"stackable", "swappable-stackable"}:
        if not sfa.bitmask_stackability_witnesses(normalized):
            return False
    if mode == "decomposition":
        if not sfa.bitmask_physics_stable(normalized):
            return False
        if not sfa.corner_columns_allowed(normalized):
            return False
        if sfa.reference_decomposition_tree(normalized, len(normalized.split(":"))) is None:
            return False
    return True


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    known_targets, suffixes = _known_zero_stack(args)
    layers = _all_layers(args.alphabet)
    lower_count = args.layers - args.suffix_width
    generated_targets: set[str] = set()
    generated_predecessors = 0
    tested = 0
    rejected_trace = rejected_push = 0
    rejected_frontier = 0
    rejected_lower = 0

    for suffix in sorted(suffixes):
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        lower_iter = itertools.product(layers, repeat=lower_count)
        for lower in lower_iter:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                break
            if args.max_candidates and tested >= args.max_candidates:
                break
            tested += 1
            lower_prefix = sfa.normalize_code(":".join(lower))
            if not _lower_prefix_allowed(lower_prefix, args.lower_filter):
                rejected_lower += 1
                continue
            predecessor = sfa.normalize_code(":".join(lower + (suffix,)))
            if not predecessor:
                continue
            if not sfa.top_single_c_zero_stack_candidate(predecessor):
                rejected_trace += 1
                continue
            if sfa.zero_stack_trace_seed(predecessor, args.layers, allow_terminal_crystal=True) is None:
                rejected_trace += 1
                continue
            target = sfa.bitmask_push_pin(predecessor, args.layers)
            if not target:
                rejected_push += 1
                continue
            if args.frontier_filter:
                target_parts = target.split(":")
                if target_parts[-1] not in TARGET_TOP_FRONTIER:
                    rejected_frontier += 1
                    continue
                removal = sfa.bitmask_layer_removal_context(target)[:3]
                if removal[0] <= 0 or not removal[1]:
                    rejected_frontier += 1
                    continue
                if sfa.claw_bottom_floor_reject_core_verdict(target) is not None:
                    rejected_frontier += 1
                    continue
            generated_predecessors += 1
            generated_targets.add(target)
        if args.max_candidates and tested >= args.max_candidates:
            break

    overlap = generated_targets & known_targets
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"suffix_width={args.suffix_width}")
    print(f"unique_suffixes={len(suffixes)}")
    print(f"known_zero_stack_targets={len(known_targets)}")
    print(f"tested={tested}")
    print(f"generated_predecessors={generated_predecessors}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"known_overlap={len(overlap)}")
    print(f"known_recall={100.0 * len(overlap) / len(known_targets) if known_targets else 100:.6f}%")
    print(f"extra_targets={len(generated_targets - known_targets)}")
    print(f"rejected_trace={rejected_trace}")
    print(f"rejected_push={rejected_push}")
    print(f"rejected_frontier={rejected_frontier}")
    print(f"rejected_lower={rejected_lower}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate claw candidates from zero-stack suffix grammar.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--suffix-width", type=int, default=4)
    parser.add_argument("--alphabet", default="-SPc")
    parser.add_argument("--frontier-filter", action="store_true")
    parser.add_argument(
        "--lower-filter",
        choices=("none", "physics", "physics-corner", "swappable", "stackable", "swappable-stackable", "decomposition"),
        default="none",
    )
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
