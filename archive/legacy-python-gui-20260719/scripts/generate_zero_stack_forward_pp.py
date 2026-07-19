from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import random
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
    if sfa.zero_stack_trace_seed(code, layers, allow_terminal_crystal=allow_terminal_crystal) is None:
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


def _rotate_layer_text(layer: str, turns: int) -> str:
    turns %= 4
    out = layer
    for _ in range(turns):
        out = out[3] + out[:3]
    return out


def _rotate_code_text(code: str, turns: int) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return ""
    return sfa.normalize_code(":".join(_rotate_layer_text(layer, turns) for layer in normalized.split(":")))


def _sorted_by_highest_c(code: str) -> str | None:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return None
    parts = normalized.split(":")
    c_positions = [(layer, q) for layer, text in enumerate(parts) for q, ch in enumerate(text) if ch == "c"]
    if not c_positions:
        return None
    highest = max(layer for layer, _q in c_positions)
    highest_qs = [q for layer, q in c_positions if layer == highest]
    if len(highest_qs) != 1:
        return None
    return _rotate_code_text(normalized, -highest_qs[0])


def _claw_common_target_allowed(code: str) -> bool:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return False
    parts = normalized.split(":")
    first = parts[0]
    c_positions = [(layer, q) for layer, text in enumerate(parts) for q, ch in enumerate(text) if ch == "c"]
    if not c_positions:
        return False
    highest = max(layer for layer, _q in c_positions)
    return (
        "c" not in first
        and sum(ch == "P" for ch in first) > 1
        and sum(ch == "S" for ch in first) < 2
        and sum(1 for layer, _q in c_positions if layer == highest) == 1
    )


def _sorted_claw_notes_target_allowed(code: str) -> bool:
    sorted_code = _sorted_by_highest_c(code)
    if sorted_code is None:
        return False
    parts = sorted_code.split(":")
    return bool(parts) and parts[-1][2] == "-" and any(layer[2] != "-" for layer in parts) and all(layer != "--c-" for layer in parts)


def _single_layer_pieces(include_crystal: bool = False) -> tuple[str, ...]:
    pieces: set[str] = set()
    for q in range(4):
        pieces.add("".join("P" if i == q else "-" for i in range(4)))
    for width in range(1, 4):
        base = "S" * width + "-" * (4 - width)
        for turns in range(4):
            pieces.add(_rotate_layer_text(base, turns))
    pieces.add("SSSS")
    if include_crystal:
        for q in range(4):
            pieces.add("".join("c" if i == q else "-" for i in range(4)))
    return tuple(sorted(pieces))


def _record_target_allowed(code: str, args: argparse.Namespace) -> bool:
    if args.target_claw_common_filter and not _claw_common_target_allowed(code):
        return False
    if args.target_sorted_claw_notes_filter and not _sorted_claw_notes_target_allowed(code):
        return False
    if args.target_strict_policy:
        strict, _reason = sfa.strict_legacy_verdict_to_symbolic(code)
        if strict != "possible":
            return False
    return True


def _predecessor_allowed(code: str, args: argparse.Namespace) -> bool:
    if args.zero_stack_only and not sfa.top_single_c_zero_stack_candidate(code):
        return False
    if args.require_trace_seed and sfa.zero_stack_trace_seed(
        code,
        args.layers,
        allow_terminal_crystal=args.allow_terminal_crystal,
    ) is None:
        return False
    if args.require_swappable and sfa.bitmask_swap_impossibility(code) is not None:
        return False
    if args.reject_processed_claw and sfa.processed_claw_fast_reject_reason(code) is not None:
        return False
    return True


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    known_predecessors, known_targets, seeds = _known(args)
    rng = random.Random(args.seed)
    seed_list = sorted(seeds)
    pieces = list(_single_layer_pieces(include_crystal=args.include_crystal_pieces))
    if args.shuffle:
        rng.shuffle(seed_list)
        rng.shuffle(pieces)
    queue = deque(seed_list)
    seen = set(seed_list)
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    rejected = Counter()
    depth_counts = Counter()
    expanded = 0

    while queue:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        current = queue.popleft()
        current_depth = len(current.split(":")) if current else 0
        if current_depth >= args.layers:
            continue
        current_pieces = list(pieces)
        if args.shuffle_each_node:
            rng.shuffle(current_pieces)
        for piece in current_pieces:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                break
            if args.max_expansions and expanded >= args.max_expansions:
                break
            expanded += 1
            stacked = sfa.bitmask_stack(current, piece, args.layers)
            if not stacked or stacked == current:
                rejected["unchanged_or_empty"] += 1
                continue
            if stacked in seen:
                rejected["duplicate"] += 1
                continue
            if len(stacked.split(":")) > args.layers:
                rejected["too_tall"] += 1
                continue
            if not _predecessor_allowed(stacked, args):
                rejected["predecessor_filter"] += 1
                continue
            seen.add(stacked)
            queue.append(stacked)
            depth_counts[len(stacked.split(":"))] += 1
            pushed = sfa.bitmask_push_pin(stacked, args.layers)
            if not pushed:
                rejected["empty_push"] += 1
                continue
            if not _record_target_allowed(pushed, args):
                rejected["target_filter"] += 1
                continue
            generated_predecessors.add(stacked)
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
    print(f"pieces={len(pieces)}")
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
    parser = argparse.ArgumentParser(description="Generate zero-stack PP candidates with a forward stack-closure prototype.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-expansions", type=int, default=0)
    parser.add_argument("--allow-terminal-crystal", action="store_true")
    parser.add_argument("--include-crystal-pieces", action="store_true")
    parser.add_argument("--zero-stack-only", action="store_true")
    parser.add_argument("--require-trace-seed", action="store_true")
    parser.add_argument("--require-swappable", action="store_true")
    parser.add_argument("--reject-processed-claw", action="store_true")
    parser.add_argument("--target-claw-common-filter", action="store_true")
    parser.add_argument("--target-sorted-claw-notes-filter", action="store_true")
    parser.add_argument("--target-strict-policy", action="store_true")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--shuffle-each-node", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
