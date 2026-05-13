from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import random
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
from generate_zero_stack_forward_pp import _claw_common_target_allowed, _sorted_claw_notes_target_allowed


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def _mask_shape(code: str, keep_mask: int) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return ""
    return sfa.normalize_code(
        ":".join(
            "".join(ch if keep_mask & (1 << q) else "-" for q, ch in enumerate(layer))
            for layer in normalized.split(":")
        )
    )


def _rotate_180(code: str) -> str:
    return sfa.bitmask_rotate_clockwise(sfa.bitmask_rotate_clockwise(code))


def _or_shape(left: str, right: str) -> str:
    left_parts = sfa.normalize_code(left).split(":") if sfa.normalize_code(left) else []
    right_parts = sfa.normalize_code(right).split(":") if sfa.normalize_code(right) else []
    depth = max(len(left_parts), len(right_parts))
    out: list[str] = []
    for index in range(depth):
        a = left_parts[index] if index < len(left_parts) else "----"
        b = right_parts[index] if index < len(right_parts) else "----"
        chars = []
        for ca, cb in zip(a, b):
            if ca != "-" and cb != "-" and ca != cb:
                return ""
            chars.append(ca if ca != "-" else cb)
        out.append("".join(chars))
    return sfa.normalize_code(":".join(out))


def _top_layer(code: str) -> str:
    normalized = sfa.normalize_code(code)
    return normalized.split(":")[-1] if normalized else "----"


def _layer_at(code: str, index: int) -> str:
    parts = sfa.normalize_code(code).split(":") if sfa.normalize_code(code) else []
    return parts[index] if index < len(parts) else "----"


def _known(
    args: argparse.Namespace,
) -> tuple[
    set[str],
    set[str],
    set[str],
    set[str],
    set[tuple[str, str]],
    set[tuple[int, str, str]],
    set[tuple[int, str, str, str, str]],
    set[tuple[int, str, str, str, str, str, str]],
    set[tuple[int, str, str, str, str, str, str, str, str]],
]:
    predecessors: set[str] = set()
    targets: set[str] = set()
    left_halves: set[str] = set()
    right_halves: set[str] = set()
    top_pairs: set[tuple[str, str]] = set()
    indexed_layer_pairs: set[tuple[int, str, str]] = set()
    indexed_transitions: set[tuple[int, str, str, str, str]] = set()
    indexed_trigrams: set[tuple[int, str, str, str, str, str, str]] = set()
    indexed_quadgrams: set[tuple[int, str, str, str, str, str, str, str, str]] = set()
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
        if not predecessor or sfa.bitmask_push_pin(predecessor, args.layers) != target:
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        predecessors.add(predecessor)
        targets.add(target)
        for angle in range(2):
            rotated = predecessor
            for _ in range(angle):
                rotated = sfa.bitmask_rotate_clockwise(rotated)
            left = _mask_shape(rotated, 0b0011)
            right = _rotate_180(_mask_shape(rotated, 0b1100))
            left_halves.add(left)
            right_halves.add(right)
            top_pairs.add((_top_layer(left), _top_layer(right)))
            for index in range(args.layers):
                indexed_layer_pairs.add((index, _layer_at(left, index), _layer_at(right, index)))
            for index in range(args.layers - 1):
                indexed_transitions.add(
                    (
                        index,
                        _layer_at(left, index),
                        _layer_at(right, index),
                        _layer_at(left, index + 1),
                        _layer_at(right, index + 1),
                    )
                )
            for index in range(args.layers - 2):
                indexed_trigrams.add(
                    (
                        index,
                        _layer_at(left, index),
                        _layer_at(right, index),
                        _layer_at(left, index + 1),
                        _layer_at(right, index + 1),
                        _layer_at(left, index + 2),
                        _layer_at(right, index + 2),
                    )
                )
            for index in range(args.layers - 3):
                indexed_quadgrams.add(
                    (
                        index,
                        _layer_at(left, index),
                        _layer_at(right, index),
                        _layer_at(left, index + 1),
                        _layer_at(right, index + 1),
                        _layer_at(left, index + 2),
                        _layer_at(right, index + 2),
                        _layer_at(left, index + 3),
                        _layer_at(right, index + 3),
                    )
                )
    return (
        predecessors,
        targets,
        left_halves,
        right_halves,
        top_pairs,
        indexed_layer_pairs,
        indexed_transitions,
        indexed_trigrams,
        indexed_quadgrams,
    )


def _target_allowed(code: str, args: argparse.Namespace) -> bool:
    if args.target_claw_common_filter and not _claw_common_target_allowed(code):
        return False
    if args.target_sorted_claw_notes_filter and not _sorted_claw_notes_target_allowed(code):
        return False
    return True


def _cheap_zero_stack_top(code: str) -> bool:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return False
    parts = normalized.split(":")
    if len(parts) < 2:
        return False
    top = parts[-1]
    return top.count("c") == 1 and all(ch in {"-", "c"} for ch in top)


def _codes_from_pair_sequence(sequence: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    left = sfa.normalize_code(":".join(item[0] for item in sequence))
    right = sfa.normalize_code(":".join(item[1] for item in sequence))
    return left, right


def _generate_sequence_pairs(
    layers: int,
    observed_indexed_layer_pairs: set[tuple[int, str, str]],
    observed_indexed_transitions: set[tuple[int, str, str, str, str]],
    max_sequences: int,
    started: float,
    max_seconds: float,
) -> tuple[list[tuple[str, str]], bool]:
    starts = sorted((left, right) for index, left, right in observed_indexed_layer_pairs if index == 0)
    transitions: dict[tuple[int, str, str], list[tuple[str, str]]] = {}
    for index, left, right, next_left, next_right in observed_indexed_transitions:
        transitions.setdefault((index, left, right), []).append((next_left, next_right))
    for values in transitions.values():
        values.sort()

    pairs: list[tuple[str, str]] = []
    truncated = False

    def rec(index: int, sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal truncated
        if truncated:
            return
        if max_seconds and time.perf_counter() - started > max_seconds:
            truncated = True
            return
        if max_sequences and len(pairs) >= max_sequences:
            truncated = True
            return
        if index == layers - 1:
            pairs.append(_codes_from_pair_sequence(sequence))
            return
        left, right = sequence[-1]
        for child in transitions.get((index, left, right), ()):
            rec(index + 1, sequence + (child,))
            if truncated:
                return

    for start in starts:
        rec(0, (start,))
        if truncated:
            break
    return pairs, truncated


def _generate_trigram_sequence_pairs(
    layers: int,
    observed_indexed_transitions: set[tuple[int, str, str, str, str]],
    observed_indexed_trigrams: set[tuple[int, str, str, str, str, str, str]],
    max_sequences: int,
    started: float,
    max_seconds: float,
) -> tuple[list[tuple[str, str]], bool]:
    starts = sorted(
        ((left, right), (next_left, next_right))
        for index, left, right, next_left, next_right in observed_indexed_transitions
        if index == 0
    )
    transitions: dict[tuple[int, str, str, str, str], list[tuple[str, str]]] = {}
    for index, left, right, mid_left, mid_right, next_left, next_right in observed_indexed_trigrams:
        transitions.setdefault((index, left, right, mid_left, mid_right), []).append((next_left, next_right))
    for values in transitions.values():
        values.sort()

    pairs: list[tuple[str, str]] = []
    truncated = False

    def rec(index: int, sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal truncated
        if truncated:
            return
        if max_seconds and time.perf_counter() - started > max_seconds:
            truncated = True
            return
        if max_sequences and len(pairs) >= max_sequences:
            truncated = True
            return
        if len(sequence) == layers:
            pairs.append(_codes_from_pair_sequence(sequence))
            return
        prev_left, prev_right = sequence[-2]
        cur_left, cur_right = sequence[-1]
        for child in transitions.get((index, prev_left, prev_right, cur_left, cur_right), ()):
            rec(index + 1, sequence + (child,))
            if truncated:
                return

    for first, second in starts:
        rec(0, (first, second))
        if truncated:
            break
    return pairs, truncated


def _generate_quadgram_sequence_pairs(
    layers: int,
    observed_indexed_trigrams: set[tuple[int, str, str, str, str, str, str]],
    observed_indexed_quadgrams: set[tuple[int, str, str, str, str, str, str, str, str]],
    max_sequences: int,
    started: float,
    max_seconds: float,
) -> tuple[list[tuple[str, str]], bool]:
    starts = sorted(
        ((left, right), (mid_left, mid_right), (next_left, next_right))
        for index, left, right, mid_left, mid_right, next_left, next_right in observed_indexed_trigrams
        if index == 0
    )
    transitions: dict[tuple[int, str, str, str, str, str, str], list[tuple[str, str]]] = {}
    for index, a_left, a_right, b_left, b_right, c_left, c_right, d_left, d_right in observed_indexed_quadgrams:
        transitions.setdefault((index, a_left, a_right, b_left, b_right, c_left, c_right), []).append((d_left, d_right))
    for values in transitions.values():
        values.sort()

    pairs: list[tuple[str, str]] = []
    truncated = False

    def rec(index: int, sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal truncated
        if truncated:
            return
        if max_seconds and time.perf_counter() - started > max_seconds:
            truncated = True
            return
        if max_sequences and len(pairs) >= max_sequences:
            truncated = True
            return
        if len(sequence) == layers:
            pairs.append(_codes_from_pair_sequence(sequence))
            return
        a_left, a_right = sequence[-3]
        b_left, b_right = sequence[-2]
        c_left, c_right = sequence[-1]
        for child in transitions.get((index, a_left, a_right, b_left, b_right, c_left, c_right), ()):
            rec(index + 1, sequence + (child,))
            if truncated:
                return

    for first, second, third in starts:
        rec(0, (first, second, third))
        if truncated:
            break
    return pairs, truncated


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    (
        known_predecessors,
        known_targets,
        left_halves,
        right_halves,
        observed_top_pairs,
        observed_indexed_layer_pairs,
        observed_indexed_transitions,
        observed_indexed_trigrams,
        observed_indexed_quadgrams,
    ) = _known(args)
    sequence_truncated = False
    if args.sequence_mode == "transitions":
        pairs, sequence_truncated = _generate_sequence_pairs(
            args.layers,
            observed_indexed_layer_pairs,
            observed_indexed_transitions,
            args.max_sequences,
            started,
            args.max_seconds,
        )
    elif args.sequence_mode == "trigrams":
        pairs, sequence_truncated = _generate_trigram_sequence_pairs(
            args.layers,
            observed_indexed_transitions,
            observed_indexed_trigrams,
            args.max_sequences,
            started,
            args.max_seconds,
        )
    elif args.sequence_mode == "quadgrams":
        pairs, sequence_truncated = _generate_quadgram_sequence_pairs(
            args.layers,
            observed_indexed_trigrams,
            observed_indexed_quadgrams,
            args.max_sequences,
            started,
            args.max_seconds,
        )
    else:
        pairs = list(itertools.product(sorted(left_halves), sorted(right_halves)))
    if args.shuffle:
        random.Random(args.seed).shuffle(pairs)
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    rejected = Counter()
    tested = 0
    for left, right in pairs:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        if args.max_pairs and tested >= args.max_pairs:
            break
        tested += 1
        if args.require_observed_top_pair and (_top_layer(left), _top_layer(right)) not in observed_top_pairs:
            rejected["top_pair"] += 1
            continue
        if args.require_observed_index_layer_pairs:
            ok = True
            for index in range(args.layers):
                if (index, _layer_at(left, index), _layer_at(right, index)) not in observed_indexed_layer_pairs:
                    ok = False
                    break
            if not ok:
                rejected["index_layer_pair"] += 1
                continue
        if args.require_observed_index_transitions:
            ok = True
            for index in range(args.layers - 1):
                transition = (
                    index,
                    _layer_at(left, index),
                    _layer_at(right, index),
                    _layer_at(left, index + 1),
                    _layer_at(right, index + 1),
                )
                if transition not in observed_indexed_transitions:
                    ok = False
                    break
            if not ok:
                rejected["index_transition"] += 1
                continue
        if args.require_observed_index_trigrams:
            ok = True
            for index in range(args.layers - 2):
                trigram = (
                    index,
                    _layer_at(left, index),
                    _layer_at(right, index),
                    _layer_at(left, index + 1),
                    _layer_at(right, index + 1),
                    _layer_at(left, index + 2),
                    _layer_at(right, index + 2),
                )
                if trigram not in observed_indexed_trigrams:
                    ok = False
                    break
            if not ok:
                rejected["index_trigram"] += 1
                continue
        if args.require_observed_index_quadgrams:
            ok = True
            for index in range(args.layers - 3):
                quadgram = (
                    index,
                    _layer_at(left, index),
                    _layer_at(right, index),
                    _layer_at(left, index + 1),
                    _layer_at(right, index + 1),
                    _layer_at(left, index + 2),
                    _layer_at(right, index + 2),
                    _layer_at(left, index + 3),
                    _layer_at(right, index + 3),
                )
                if quadgram not in observed_indexed_quadgrams:
                    ok = False
                    break
            if not ok:
                rejected["index_quadgram"] += 1
                continue
        predecessor = _or_shape(left, _rotate_180(right))
        if not predecessor:
            rejected["overlap_conflict"] += 1
            continue
        if len(predecessor.split(":")) > args.layers:
            rejected["too_tall"] += 1
            continue
        if args.require_zero_stack and not _cheap_zero_stack_top(predecessor):
            rejected["not_zero_stack_top"] += 1
            continue
        if args.require_zero_stack and not sfa.top_single_c_zero_stack_candidate(predecessor):
            rejected["not_zero_stack"] += 1
            continue
        if args.require_trace_seed and sfa.zero_stack_trace_seed(predecessor, args.layers, allow_terminal_crystal=True) is None:
            rejected["no_trace_seed"] += 1
            continue
        generated_predecessors.add(predecessor)
        if not args.predecessor_only:
            pushed = sfa.bitmask_push_pin(predecessor, args.layers)
            if not pushed:
                rejected["empty_push"] += 1
                continue
            if not _target_allowed(pushed, args):
                rejected["target_filter"] += 1
                continue
            generated_targets.add(pushed)

    predecessor_overlap = generated_predecessors & known_predecessors
    target_overlap = generated_targets & known_targets
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"known_zero_stack_predecessors={len(known_predecessors)}")
    print(f"known_zero_stack_targets={len(known_targets)}")
    print(f"left_halves={len(left_halves)}")
    print(f"right_halves={len(right_halves)}")
    print(f"observed_top_pairs={len(observed_top_pairs)}")
    print(f"observed_indexed_layer_pairs={len(observed_indexed_layer_pairs)}")
    print(f"observed_indexed_transitions={len(observed_indexed_transitions)}")
    print(f"observed_indexed_trigrams={len(observed_indexed_trigrams)}")
    print(f"observed_indexed_quadgrams={len(observed_indexed_quadgrams)}")
    print(f"pair_space={len(pairs)}")
    print(f"sequence_truncated={sequence_truncated}")
    print(f"tested={tested}")
    print(f"generated_predecessors={len(generated_predecessors)}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"predecessor_overlap={len(predecessor_overlap)}")
    print(f"predecessor_recall={100.0 * len(predecessor_overlap) / len(known_predecessors) if known_predecessors else 100:.6f}%")
    print(f"predecessor_extra={len(generated_predecessors - known_predecessors)}")
    print(f"target_overlap={len(target_overlap)}")
    print(f"target_recall={100.0 * len(target_overlap) / len(known_targets) if known_targets else 100:.6f}%")
    print(f"target_extra={len(generated_targets - known_targets)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("rejected:")
    for key, count in rejected.most_common():
        print(f"  {key}: {count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate zero-stack claw candidates from observed half-language pairs.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--require-zero-stack", action="store_true")
    parser.add_argument("--require-trace-seed", action="store_true")
    parser.add_argument("--target-claw-common-filter", action="store_true")
    parser.add_argument("--target-sorted-claw-notes-filter", action="store_true")
    parser.add_argument("--require-observed-top-pair", action="store_true")
    parser.add_argument("--require-observed-index-layer-pairs", action="store_true")
    parser.add_argument("--require-observed-index-transitions", action="store_true")
    parser.add_argument("--require-observed-index-trigrams", action="store_true")
    parser.add_argument("--require-observed-index-quadgrams", action="store_true")
    parser.add_argument("--sequence-mode", choices=("cartesian", "transitions", "trigrams", "quadgrams"), default="cartesian")
    parser.add_argument("--max-sequences", type=int, default=0)
    parser.add_argument("--predecessor-only", action="store_true")
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
