from __future__ import annotations

import argparse
import contextlib
import io
import json
import random
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
from generate_zero_stack_forward_pp import _claw_common_target_allowed, _sorted_claw_notes_target_allowed
from generate_zero_stack_half_pair_candidates import _mask_shape, _or_shape, _rotate_180
from validate_half_pair_ngram_generalization import _abstract_layer, _ngram_index

with contextlib.redirect_stdout(io.StringIO()):
    from claw_tracer import claw_process as _claw_process
    from data_operations import simplify_shape as _simplify_shape
    from shape import Shape as _Shape


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        raw = _claw_process(repr(_Shape.from_string(code)))
        return sfa.normalize_code(_simplify_shape(raw) if raw else "")


def _layer_at(code: str, index: int) -> str:
    parts = sfa.normalize_code(code).split(":") if sfa.normalize_code(code) else []
    return parts[index] if index < len(parts) else "----"


def _pair_sequence(predecessor: str, layers: int, angle: int) -> tuple[tuple[str, str], ...]:
    rotated = predecessor
    for _ in range(angle):
        rotated = sfa.bitmask_rotate_clockwise(rotated)
    left = _mask_shape(rotated, 0b0011)
    right = _rotate_180(_mask_shape(rotated, 0b1100))
    return tuple((_layer_at(left, index), _layer_at(right, index)) for index in range(layers))


def _abstract_pair(pair: tuple[str, str], mode: str) -> tuple[str, str]:
    return _abstract_layer(pair[0], mode), _abstract_layer(pair[1], mode)


def _train(args: argparse.Namespace):
    started = time.perf_counter()
    max_train_seconds = args.max_train_seconds or args.max_seconds
    abstract_ngrams: set[tuple[int, tuple[tuple[str, str], ...]]] = set()
    raw_by_abstract: defaultdict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    raw_pair_counts: Counter[tuple[str, str]] = Counter()
    records = 0
    total = 0
    for code in sfa.iter_data_codes(args.data, max_layers=args.train_layers):
        if args.limit and total >= args.limit:
            break
        if max_train_seconds and time.perf_counter() - started > max_train_seconds:
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, args.train_layers) != target:
            continue
        subtype = sfa.pp_subtype_candidate(predecessor, args.train_layers).subtype
        if subtype != "top_single_c_zero_stack_unresolved_pp_candidate":
            continue
        records += 1
        for angle in range(2):
            sequence = _pair_sequence(predecessor, args.train_layers, angle)
            abstract_sequence = tuple(_abstract_pair(pair, args.abstract_mode) for pair in sequence)
            for pair, abstract in zip(sequence, abstract_sequence):
                raw_by_abstract[abstract].add(pair)
                raw_pair_counts[pair] += 1
            for index in range(len(abstract_sequence) - args.order + 1):
                gram = abstract_sequence[index : index + args.order]
                abstract_ngrams.add((_ngram_index(index, len(abstract_sequence), args.order, "top_relative"), gram))
                abstract_ngrams.add((-1, gram))
    return records, abstract_ngrams, raw_by_abstract, raw_pair_counts


def _abstract_sequences(args: argparse.Namespace, abstract_ngrams: set[tuple[int, tuple[tuple[str, str], ...]]]):
    starts = sorted(gram for index, gram in abstract_ngrams if index == -1)
    transitions: dict[tuple[int, tuple[tuple[str, str], ...]], list[tuple[str, str]]] = {}
    for index, gram in abstract_ngrams:
        transitions.setdefault((index, gram[:-1]), []).append(gram[-1])
    for values in transitions.values():
        values.sort()
    sequences: list[tuple[tuple[str, str], ...]] = []
    truncated = False
    started = time.perf_counter()

    def rec(sequence: tuple[tuple[str, str], ...]) -> None:
        nonlocal truncated
        if truncated:
            return
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            truncated = True
            return
        if args.max_abstract_sequences and len(sequences) >= args.max_abstract_sequences:
            truncated = True
            return
        if len(sequence) == args.generate_layers:
            sequences.append(sequence)
            return
        raw_index = len(sequence) - args.order + 1
        top_relative = _ngram_index(raw_index, args.generate_layers, args.order, "top_relative")
        min_train_top_relative = -(args.train_layers - args.order)
        index = -1 if top_relative < min_train_top_relative else top_relative
        for child in transitions.get((index, sequence[-(args.order - 1) :]), ()):
            rec(sequence + (child,))
            if truncated:
                return

    for start in starts:
        rec(start)
        if truncated:
            break
    return sequences, truncated


def _raw_sequences_for(
    abstract_sequence: tuple[tuple[str, str], ...],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
    max_per_layer: int,
    rng: random.Random,
):
    choices: list[list[tuple[str, str]]] = []
    for abstract in abstract_sequence:
        raw = sorted(raw_by_abstract.get(abstract, ()), key=lambda item: (-raw_pair_counts[item], item))
        if not raw:
            return []
        if max_per_layer and len(raw) > max_per_layer:
            head = raw[:max_per_layer]
            if len(raw) > max_per_layer * 2:
                tail = rng.sample(raw[max_per_layer:], max_per_layer)
                raw = head + tail
            else:
                raw = head
        choices.append(raw)
    out: list[tuple[tuple[str, str], ...]] = [()]
    for layer_choices in choices:
        out = [prefix + (choice,) for prefix in out for choice in layer_choices]
        if len(out) > 100_000:
            out = out[:100_000]
    return out


def _predecessor_from_sequence(sequence: tuple[tuple[str, str], ...]) -> str:
    left = sfa.normalize_code(":".join(pair[0] for pair in sequence))
    right = sfa.normalize_code(":".join(pair[1] for pair in sequence))
    return _or_shape(left, _rotate_180(right))


def generate(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    rng = random.Random(args.seed)
    records, abstract_ngrams, raw_by_abstract, raw_pair_counts = _train(args)
    abstract_sequences, abstract_truncated = _abstract_sequences(args, abstract_ngrams)
    if args.shuffle:
        rng.shuffle(abstract_sequences)

    tested_raw = 0
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    rejected = Counter()
    target_features = Counter()
    predecessor_features = Counter()
    target_verdicts = Counter()
    target_kernel_verdicts = Counter()
    predecessor_subtypes = Counter()
    predecessor_stackability = Counter()
    predecessor_seed_status = Counter()
    selected_rows: list[str] = []
    selected_records: list[dict[str, object]] = []
    for abstract_sequence in abstract_sequences:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        raw_sequences = _raw_sequences_for(abstract_sequence, raw_by_abstract, raw_pair_counts, args.max_raw_per_layer, rng)
        for raw_sequence in raw_sequences:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                break
            if args.max_raw_tests and tested_raw >= args.max_raw_tests:
                break
            tested_raw += 1
            predecessor = _predecessor_from_sequence(raw_sequence)
            if not predecessor:
                rejected["overlap"] += 1
                continue
            if not sfa.top_single_c_zero_stack_candidate(predecessor):
                rejected["not_zero_stack"] += 1
                continue
            pushed = sfa.bitmask_push_pin(predecessor, args.generate_layers)
            if not pushed:
                rejected["empty_push"] += 1
                continue
            if args.target_claw_common_filter and not _claw_common_target_allowed(pushed):
                rejected["target_common"] += 1
                continue
            if args.target_sorted_claw_notes_filter and not _sorted_claw_notes_target_allowed(pushed):
                rejected["target_notes"] += 1
                continue
            if args.target_corner_filter and not sfa.corner_columns_allowed(pushed):
                rejected["target_corner"] += 1
                continue
            if args.target_swap_both_filter and sfa.bitmask_swap_impossibility(pushed) != "swap_both_blocked":
                rejected["target_swap"] += 1
                continue
            if args.target_removed_crystal_filter and not sfa.bitmask_layer_removal_context(pushed)[1]:
                rejected["target_removed_crystal"] += 1
                continue
            seed = sfa.zero_stack_trace_seed(
                predecessor,
                args.generate_layers,
                allow_terminal_crystal=True,
            )
            if seed is None:
                predecessor_seed_status["missing_zero_stack_seed"] += 1
                if args.require_seed_stackable:
                    rejected["missing_zero_stack_seed"] += 1
                    continue
            else:
                seed_current, _seed_base = seed
                seed_stackable = bool(sfa.bitmask_stackability_witnesses(seed_current))
                predecessor_seed_status["seed_stackable" if seed_stackable else "seed_nonstackable"] += 1
                if args.require_seed_stackable and not seed_stackable:
                    rejected["seed_nonstackable"] += 1
                    continue
            generated_predecessors.add(predecessor)
            generated_targets.add(pushed)
            predecessor_subtypes[sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype] += 1
            predecessor_stackability[str(bool(sfa.bitmask_stackability_witnesses(predecessor)))] += 1
            if args.classify_targets:
                strict, reason = sfa.strict_legacy_verdict_to_symbolic(pushed)
                target_verdicts[(strict, reason)] += 1
                kernel_verdict = None
                if strict == "impossible" and "corner_rule" in reason:
                    kernel_verdict = (strict, reason)
                else:
                    for kernel_fn in (
                        sfa.swap_core_verdict,
                        sfa.zero_stack_terminal_crystal_pp_predecessor_core_verdict,
                        sfa.zero_stack_terminal_crystal_failure_core_verdict,
                        sfa.claw_failure_core_verdict,
                    ):
                        kernel_verdict = kernel_fn(pushed, args.generate_layers) if kernel_fn.__name__.startswith("zero_stack") else kernel_fn(pushed)
                        if kernel_verdict is not None:
                            break
                target_kernel_verdicts[kernel_verdict or (strict, reason)] += 1
                capture_reasons = set(args.capture_kernel_reason)
                effective_kernel_verdict = kernel_verdict or (strict, reason)
                if strict in set(args.capture_verdict) or effective_kernel_verdict[1] in capture_reasons:
                    if len(selected_records) < args.max_capture:
                        seed = sfa.zero_stack_trace_seed(
                            predecessor,
                            args.generate_layers,
                            allow_terminal_crystal=True,
                        )
                        seed_current = seed[0] if seed else ""
                        seed_base = seed[1] if seed else ""
                        seed_witnesses = sfa.bitmask_stackability_witnesses(seed_current) if seed_current else ()
                        predecessor_physics = sfa.bitmask_apply_physics(predecessor)
                        selected_records.append(
                            {
                                "verdict": strict,
                                "reason": reason,
                                "kernel_verdict": effective_kernel_verdict[0],
                                "kernel_reason": effective_kernel_verdict[1],
                                "target": pushed,
                                "predecessor": predecessor,
                                "predecessor_subtype": sfa.pp_subtype_candidate(
                                    predecessor, args.generate_layers
                                ).subtype,
                                "predecessor_stackable": bool(
                                    sfa.bitmask_stackability_witnesses(predecessor)
                                ),
                                "predecessor_stable": predecessor_physics == predecessor,
                                "predecessor_physics": predecessor_physics,
                                "predecessor_physics_push_matches": (
                                    sfa.bitmask_push_pin(predecessor_physics, args.generate_layers) == pushed
                                    if predecessor_physics
                                    else False
                                ),
                                "predecessor_swap": sfa.bitmask_swap_impossibility(predecessor)
                                or "swappable",
                                "target_swap": sfa.bitmask_swap_impossibility(pushed) or "swappable",
                                "target_layer_removal": sfa.bitmask_layer_removal_context(pushed)[:3],
                                "zero_stack_seed_current": seed_current,
                                "zero_stack_seed_base": seed_base,
                                "zero_stack_seed_stackable": bool(seed_witnesses),
                                "zero_stack_seed_witnesses": [
                                    {
                                        "base": witness.base,
                                        "delta": witness.stacked_delta,
                                        "heights": witness.heights,
                                    }
                                    for witness in seed_witnesses[: args.max_capture_witnesses]
                                ],
                                "abstract_sequence": abstract_sequence,
                                "raw_sequence": raw_sequence,
                            }
                        )
                    if len(selected_rows) < args.max_capture:
                        selected_rows.append(
                            f"{strict}\t{reason}\t"
                            f"kernel={effective_kernel_verdict[0]}/{effective_kernel_verdict[1]}\t"
                            f"T={pushed}\tA={predecessor}"
                        )
            p_parts = predecessor.split(":") if predecessor else []
            t_parts = pushed.split(":") if pushed else []
            predecessor_features[(
                f"layers={len(p_parts)}",
                f"top={p_parts[-1] if p_parts else '----'}",
                f"swap={sfa.bitmask_swap_impossibility(predecessor) or 'swappable'}",
            )] += 1
            target_features[(
                f"layers={len(t_parts)}",
                f"first={t_parts[0] if t_parts else '----'}",
                f"top={t_parts[-1] if t_parts else '----'}",
                f"swap={sfa.bitmask_swap_impossibility(pushed) or 'swappable'}",
                f"removal={sfa.bitmask_layer_removal_context(pushed)[:3]}",
            )] += 1
        if args.max_raw_tests and tested_raw >= args.max_raw_tests:
            break

    print(f"input={args.data}")
    print(f"train_layers={args.train_layers}")
    print(f"generate_layers={args.generate_layers}")
    print(f"order={args.order}")
    print(f"abstract_mode={args.abstract_mode}")
    print(f"records={records}")
    print(f"abstract_ngrams={len(abstract_ngrams)}")
    print(f"abstract_classes={len(raw_by_abstract)}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"tested_raw={tested_raw}")
    print(f"generated_predecessors={len(generated_predecessors)}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("rejected:")
    for key, count in rejected.most_common():
        print(f"  {key}: {count}")
    print("target_features:")
    for key, count in target_features.most_common(args.top):
        print(f"  {key}: {count}")
    print("predecessor_features:")
    for key, count in predecessor_features.most_common(args.top):
        print(f"  {key}: {count}")
    print("predecessor_subtypes:")
    for key, count in predecessor_subtypes.most_common(args.top):
        print(f"  {key}: {count}")
    print("predecessor_stackability:")
    for key, count in predecessor_stackability.most_common(args.top):
        print(f"  {key}: {count}")
    print("predecessor_seed_status:")
    for key, count in predecessor_seed_status.most_common(args.top):
        print(f"  {key}: {count}")
    if args.classify_targets:
        print("target_verdicts:")
        for key, count in target_verdicts.most_common(args.top):
            print(f"  {key}: {count}")
        print("target_kernel_verdicts:")
        for key, count in target_kernel_verdicts.most_common(args.top):
            print(f"  {key}: {count}")
    if selected_rows:
        print("captured:")
        for row in selected_rows:
            print(row)
    if args.write_captured and selected_records:
        args.write_captured.parent.mkdir(parents=True, exist_ok=True)
        with args.write_captured.open("w", encoding="utf-8") as handle:
            for record in selected_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"captured_written={args.write_captured}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate exploratory 6-layer claw candidates from abstract half-pair automaton.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--train-layers", type=int, default=5)
    parser.add_argument("--generate-layers", type=int, default=6)
    parser.add_argument("--order", type=int, default=3)
    parser.add_argument("--abstract-mode", choices=("classes", "mask_counts"), default="classes")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-train-seconds", type=float, default=0.0)
    parser.add_argument("--max-abstract-sequences", type=int, default=50000)
    parser.add_argument("--max-raw-per-layer", type=int, default=3)
    parser.add_argument("--max-raw-tests", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--target-claw-common-filter", action="store_true")
    parser.add_argument("--target-sorted-claw-notes-filter", action="store_true")
    parser.add_argument("--target-corner-filter", action="store_true")
    parser.add_argument("--target-swap-both-filter", action="store_true")
    parser.add_argument("--target-removed-crystal-filter", action="store_true")
    parser.add_argument("--require-seed-stackable", action="store_true")
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--classify-targets", action="store_true")
    parser.add_argument("--capture-verdict", action="append", default=[])
    parser.add_argument("--capture-kernel-reason", action="append", default=[])
    parser.add_argument("--max-capture", type=int, default=20)
    parser.add_argument("--max-capture-witnesses", type=int, default=4)
    parser.add_argument("--write-captured", type=Path)
    return generate(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
