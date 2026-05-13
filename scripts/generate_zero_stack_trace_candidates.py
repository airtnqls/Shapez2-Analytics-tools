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


def _column_height(parts: list[str], q: int) -> int:
    height = 0
    for index, layer in enumerate(parts):
        if layer[q] != "-":
            height = index + 1
    return height


def _pin_push_gap_signature(code: str, max_layers: int) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return "empty"
    parts = normalized.split(":")
    source_layers = [list(layer) for layer in parts]
    pin_layer = ["P" if ch != "-" else "-" for ch in source_layers[0]]
    shifted_layers = [pin_layer] + [layer[:] for layer in source_layers]
    destroyed = {
        (layer, q)
        for layer in range(max_layers, len(shifted_layers))
        for q in range(4)
        if sfa._piece_at(shifted_layers, layer, q) != "-"
    }
    shattered = sfa._shatter_set(shifted_layers, destroyed) if destroyed else set()
    kept_shattered = {(layer, q) for layer, q in shattered if 0 <= layer < max_layers}
    top_gaps: list[tuple[int, int]] = []
    for q in range(4):
        column_shatter = [layer for layer, sq in kept_shattered if sq == q]
        if not column_shatter:
            continue
        shifted_layer = max(column_shatter)
        original_layer = shifted_layer - 1
        if original_layer < 0 or original_layer >= max_layers - 2:
            continue
        if shifted_layer != _column_height(parts, q):
            continue
        top_gaps.append((original_layer, q))
    destroyed_cols = "".join(str(q) for _layer, q in sorted(destroyed)) or "-"
    gap_cols = "".join(str(q) for _layer, q in sorted(top_gaps)) or "-"
    gap_layers = ",".join(str(layer) for layer, _q in sorted(top_gaps)) or "-"
    return (
        f"destroyed={len(destroyed)}:{destroyed_cols}"
        f"|shatter={len(shattered)}"
        f"|kept={len(kept_shattered)}"
        f"|gaps={len(top_gaps)}:{gap_layers}:{gap_cols}"
    )


def _pin_push_after_shatter_code(code: str, max_layers: int) -> tuple[str, int]:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return "", 0
    source_layers = [list(layer) for layer in normalized.split(":")]
    pin_layer = ["P" if ch != "-" else "-" for ch in source_layers[0]]
    layers = [pin_layer] + [layer[:] for layer in source_layers]
    destroyed = {
        (layer, q)
        for layer in range(max_layers, len(layers))
        for q in range(4)
        if sfa._piece_at(layers, layer, q) != "-"
    }
    shattered = sfa._shatter_set(layers, destroyed) if destroyed else set()
    for layer, q in shattered:
        if 0 <= layer < len(layers):
            layers[layer][q] = "-"
    layers = layers[:max_layers]
    sfa._trim_layers(layers)
    return sfa.normalize_code(":".join("".join(layer) for layer in layers)), len(shattered)


def _future_pin_interaction_possible(code: str, max_layers: int) -> bool:
    after_shatter, shatter_count = _pin_push_after_shatter_code(code, max_layers)
    if not after_shatter:
        return False
    if shatter_count == 0:
        return False
    return sfa.bitmask_apply_physics(after_shatter) != after_shatter


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


def _claw_common_target_allowed(code: str) -> bool:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return False
    parts = normalized.split(":")
    first = parts[0]
    if "c" in first:
        return False
    if sum(ch == "P" for ch in first) <= 1:
        return False
    if sum(ch == "S" for ch in first) >= 2:
        return False
    c_positions = [(layer, q) for layer, text in enumerate(parts) for q, ch in enumerate(text) if ch == "c"]
    if not c_positions:
        return False
    highest = max(layer for layer, _q in c_positions)
    if sum(1 for layer, _q in c_positions if layer == highest) != 1:
        return False
    for text in parts:
        if text == "--c-":
            return False
    return True


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


def _sorted_claw_notes_target_allowed(code: str) -> bool:
    sorted_code = _sorted_by_highest_c(code)
    if sorted_code is None:
        return False
    parts = sorted_code.split(":")
    if not parts:
        return False
    if parts[-1][2] != "-":
        return False
    for layer in parts[: min(3, len(parts))]:
        if layer[2] == "-":
            return False
    if any(layer == "--c-" for layer in parts):
        return False
    return True


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    known_predecessors, known_targets, seeds = _known(args)
    rng = random.Random(args.seed)
    layers_list = list(_all_layers(args.alphabet))
    seed_list = sorted(seeds)
    if args.shuffle:
        rng.shuffle(layers_list)
        rng.shuffle(seed_list)
    layers = tuple(layers_list)
    queue = deque(seed_list)
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
        if args.prune_no_future_pin_interaction and not _future_pin_interaction_possible(current, args.layers):
            rejected["no_future_pin_interaction"] += 1
            continue
        current_layers = list(layers)
        if args.shuffle_each_node:
            rng.shuffle(current_layers)
        for layer in current_layers:
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
                    if args.target_claw_common_filter and not _claw_common_target_allowed(pushed):
                        rejected["target_claw_common"] += 1
                        continue
                    if args.target_sorted_claw_notes_filter and not _sorted_claw_notes_target_allowed(pushed):
                        rejected["target_sorted_claw_notes"] += 1
                        continue
                    generated_targets.add(pushed)
        if args.max_expansions and expanded >= args.max_expansions:
            break

    predecessor_overlap = generated_predecessors & known_predecessors
    target_overlap = generated_targets & known_targets
    known_gap_counts = Counter(_pin_push_gap_signature(code, args.layers) for code in known_predecessors)
    overlap_gap_counts = Counter(_pin_push_gap_signature(code, args.layers) for code in predecessor_overlap)
    extra_gap_counts = Counter(_pin_push_gap_signature(code, args.layers) for code in generated_predecessors - known_predecessors)
    known_common_pass = sum(1 for code in known_targets if _claw_common_target_allowed(code))
    known_sorted_notes_pass = sum(1 for code in known_targets if _sorted_claw_notes_target_allowed(code))
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"known_zero_stack_predecessors={len(known_predecessors)}")
    print(f"known_zero_stack_targets={len(known_targets)}")
    print(f"known_target_claw_common_pass={known_common_pass}")
    print(f"known_target_sorted_claw_notes_pass={known_sorted_notes_pass}")
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
    for title, counter in (
        ("known_gap_counts", known_gap_counts),
        ("overlap_gap_counts", overlap_gap_counts),
        ("extra_gap_counts", extra_gap_counts),
    ):
        print(f"{title}:")
        for key, count in counter.most_common(args.top):
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
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--shuffle-each-node", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--target-claw-common-filter", action="store_true")
    parser.add_argument("--target-sorted-claw-notes-filter", action="store_true")
    parser.add_argument("--prune-no-future-pin-interaction", action="store_true")
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
