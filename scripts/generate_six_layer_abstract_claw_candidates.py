from __future__ import annotations

import argparse
import contextlib
import io
import json
import pickle
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


DEFAULT_TRAIN_SUBTYPES = ("top_single_c_zero_stack_unresolved_pp_candidate",)
ALL_PP_TRAIN_SUBTYPES = (
    "direct_pp_candidate",
    "mid_stack_delta_pp_candidate",
    "top_single_c_zero_stack_unresolved_pp_candidate",
)
KERNEL_STEP_TIMING: Counter[str] = Counter()
KERNEL_STEP_COUNTS: Counter[str] = Counter()
TRAINING_CACHE_VERSION = 1
FAST_TERMINAL_REASONS = frozenset(
    {
        "kernel_claw_top_crystal_shift_predecessor",
        "kernel_claw_obvious_unstable_predecessor",
        "kernel_claw_obvious_unstable_predecessor_rot1",
        "kernel_claw_obvious_unstable_predecessor_rot2",
        "kernel_claw_obvious_unstable_predecessor_rot3",
        "kernel_claw_terminal_s_sc_zero_stack",
        "kernel_claw_terminal_s_sc_zero_stack_rot1",
        "kernel_claw_terminal_s_sc_zero_stack_rot2",
        "kernel_claw_terminal_s_sc_zero_stack_rot3",
        "kernel_claw_terminal_s_sc_double_support",
        "kernel_claw_terminal_s_sc_double_support_rot1",
        "kernel_claw_terminal_s_sc_double_support_rot2",
        "kernel_claw_terminal_s_sc_double_support_rot3",
        "kernel_claw_terminal_s_sc_invalid_support",
        "kernel_claw_terminal_s_sc_invalid_support_rot1",
        "kernel_claw_terminal_s_sc_invalid_support_rot2",
        "kernel_claw_terminal_s_sc_invalid_support_rot3",
        "kernel_claw_terminal_s_sc_unstable_tail",
        "kernel_claw_terminal_s_sc_unstable_tail_rot1",
        "kernel_claw_terminal_s_sc_unstable_tail_rot2",
        "kernel_claw_terminal_s_sc_unstable_tail_rot3",
        "kernel_claw_terminal_s_sc_unstable_crystal_tail",
        "kernel_claw_terminal_s_sc_unstable_crystal_tail_rot1",
        "kernel_claw_terminal_s_sc_unstable_crystal_tail_rot2",
        "kernel_claw_terminal_s_sc_unstable_crystal_tail_rot3",
        "kernel_claw_terminal_s_sc_invalid_mid_support",
        "kernel_claw_terminal_s_sc_invalid_mid_support_rot1",
        "kernel_claw_terminal_s_sc_invalid_mid_support_rot2",
        "kernel_claw_terminal_s_sc_invalid_mid_support_rot3",
    }
)


def _selected_subtypes(value: str) -> tuple[str, ...]:
    if value == "zero_stack":
        return DEFAULT_TRAIN_SUBTYPES
    if value == "all_pp":
        return ALL_PP_TRAIN_SUBTYPES
    return tuple(part.strip() for part in value.split(",") if part.strip())


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
        if subtype not in args.selected_train_subtypes:
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


def _training_cache_metadata(args: argparse.Namespace) -> dict[str, object]:
    data_path = args.data.resolve()
    stat = data_path.stat() if data_path.exists() else None
    return {
        "version": TRAINING_CACHE_VERSION,
        "data": str(data_path),
        "data_mtime_ns": stat.st_mtime_ns if stat else None,
        "data_size": stat.st_size if stat else None,
        "train_layers": args.train_layers,
        "generate_layers": args.generate_layers,
        "order": args.order,
        "abstract_mode": args.abstract_mode,
        "limit": args.limit,
        "selected_train_subtypes": tuple(args.selected_train_subtypes),
        "max_abstract_sequences": args.max_abstract_sequences,
    }


def _load_training_cache(args: argparse.Namespace):
    if args.read_training_cache is None or not args.read_training_cache.exists():
        return None
    with args.read_training_cache.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict) or payload.get("metadata") != _training_cache_metadata(args):
        return None
    required = (
        "records",
        "abstract_ngrams",
        "raw_by_abstract",
        "raw_pair_counts",
        "abstract_sequences",
        "abstract_truncated",
    )
    if any(key not in payload for key in required):
        return None
    return (
        payload["records"],
        payload["abstract_ngrams"],
        payload["raw_by_abstract"],
        payload["raw_pair_counts"],
        payload["abstract_sequences"],
        payload["abstract_truncated"],
    )


def _write_training_cache(args: argparse.Namespace, pretrained) -> None:
    if args.write_training_cache is None:
        return
    records, abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    payload = {
        "metadata": _training_cache_metadata(args),
        "records": records,
        "abstract_ngrams": abstract_ngrams,
        "raw_by_abstract": raw_by_abstract,
        "raw_pair_counts": raw_pair_counts,
        "abstract_sequences": abstract_sequences,
        "abstract_truncated": abstract_truncated,
    }
    try:
        args.write_training_cache.parent.mkdir(parents=True, exist_ok=True)
        with args.write_training_cache.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError as exc:
        print(f"training_cache_write_failed={args.write_training_cache} reason={exc}")


def _load_or_train(args: argparse.Namespace):
    started = time.perf_counter()
    cached = _load_training_cache(args)
    if cached is not None:
        return cached, 0.0, 0.0, True

    records, abstract_ngrams, raw_by_abstract, raw_pair_counts = _train(args)
    trained_at = time.perf_counter()
    abstract_sequences, abstract_truncated = _abstract_sequences(args, abstract_ngrams)
    sequenced_at = time.perf_counter()
    pretrained = (records, abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated)
    _write_training_cache(args, pretrained)
    return pretrained, trained_at - started, sequenced_at - trained_at, False


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


def _kernel_verdict_for_target(
    target: str,
    layers: int,
    *,
    use_generated_predecessor_evidence: bool = False,
    predecessor: str = "",
    use_fast_terminal_rules: bool = True,
) -> tuple[str, str]:
    strict, reason = sfa.strict_legacy_verdict_to_symbolic(target)
    kernel_verdict = sfa.corner_rule_core_verdict(target)
    if kernel_verdict is None:
        if use_generated_predecessor_evidence and predecessor:
            predecessor = sfa.normalize_code(predecessor)
            if (
                sfa.bitmask_physics_stable(predecessor)
                and sfa.bitmask_push_pin(predecessor, layers) == sfa.normalize_code(target)
                and sfa.claw_change_rule_predecessor_is_explainable(predecessor, layers)
            ):
                return "possible", "kernel_generated_predecessor_explainable_trace"
        if use_fast_terminal_rules:
            if sfa.claw_top_crystal_shift_predecessor_witness(target, layers) is not None:
                return "possible", "kernel_claw_top_crystal_shift_predecessor"
            kernel_verdict = sfa.claw_obvious_unstable_predecessor_core_verdict(target, layers)
            if kernel_verdict is not None:
                return kernel_verdict
            kernel_verdict = sfa.claw_terminal_s_sc_core_verdict(target, layers)
            if kernel_verdict is not None:
                return kernel_verdict
        for kernel_fn in (
            sfa.swap_core_verdict,
            sfa.zero_stack_terminal_crystal_pp_predecessor_core_verdict,
            sfa.claw_change_rule_predecessor_core_verdict,
            sfa.zero_stack_terminal_crystal_failure_core_verdict,
            sfa.generic_viable_pin_push_predecessor_core_verdict,
            sfa.claw_unstable_predecessor_core_verdict,
        ):
            tick = time.perf_counter()
            kernel_verdict = (
                kernel_fn(target, layers)
                if kernel_fn.__name__.startswith(("zero_stack", "claw_change_rule", "claw_unstable", "generic_viable"))
                else kernel_fn(target)
            )
            step_name = kernel_fn.__name__.removesuffix("_core_verdict")
            KERNEL_STEP_TIMING[step_name] += time.perf_counter() - tick
            KERNEL_STEP_COUNTS[step_name] += 1
            if kernel_verdict is not None:
                break
        if kernel_verdict is None and layers <= sfa.MAX_LAYERS:
            kernel_verdict = sfa.claw_failure_core_verdict(target)
        if kernel_verdict is None and use_generated_predecessor_evidence and predecessor:
            predecessor_physics = sfa.bitmask_apply_physics(predecessor)
            if predecessor_physics != predecessor:
                kernel_verdict = (
                    "impossible",
                    "kernel_generated_predecessor_unstable_trace",
                )
            elif (
                sfa.bitmask_push_pin(predecessor, layers) == sfa.normalize_code(target)
                and sfa.claw_change_rule_predecessor_is_explainable(predecessor, layers)
            ):
                kernel_verdict = (
                    "possible",
                    "kernel_generated_predecessor_explainable_trace",
                )
    return kernel_verdict or (strict, reason)


def generate(args: argparse.Namespace, pretrained=None) -> int:
    started = time.perf_counter()
    KERNEL_STEP_TIMING.clear()
    KERNEL_STEP_COUNTS.clear()
    rng = random.Random(args.seed)
    if pretrained is None:
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
        records, abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    else:
        records, abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
        training_time = 0.0
        sequence_time = 0.0
        training_cache_hit = False
    if args.shuffle:
        rng.shuffle(abstract_sequences)

    tested_raw = 0
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    listed_predecessors: set[str] = set()
    listed_targets: set[str] = set()
    rejected = Counter()
    target_features = Counter()
    predecessor_features = Counter()
    target_verdicts = Counter()
    target_kernel_verdicts = Counter()
    candidate_source_hits = Counter()
    predecessor_subtypes = Counter()
    predecessor_stackability = Counter()
    predecessor_seed_status = Counter()
    timing = Counter()
    fast_terminal_audit_mismatches = 0
    fast_terminal_audit_samples: list[str] = []
    selected_rows: list[str] = []
    selected_records: list[dict[str, object]] = []
    stop_reason = "exhausted"
    for abstract_sequence in abstract_sequences:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            stop_reason = "max_seconds"
            break
        raw_sequences = _raw_sequences_for(abstract_sequence, raw_by_abstract, raw_pair_counts, args.max_raw_per_layer, rng)
        for raw_sequence in raw_sequences:
            if args.max_seconds and time.perf_counter() - started > args.max_seconds:
                stop_reason = "max_seconds"
                break
            if args.max_raw_tests and tested_raw >= args.max_raw_tests:
                stop_reason = "max_raw_tests"
                break
            tested_raw += 1
            predecessor = _predecessor_from_sequence(raw_sequence)
            if not predecessor:
                rejected["overlap"] += 1
                continue
            predecessor_subtype = sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype
            if predecessor_subtype not in args.selected_generate_subtypes:
                rejected["subtype"] += 1
                continue
            if not args.allow_non_zero_stack_predecessor and not sfa.top_single_c_zero_stack_candidate(predecessor):
                rejected["not_zero_stack"] += 1
                continue
            pushed = sfa.bitmask_push_pin(predecessor, args.generate_layers)
            if not pushed:
                rejected["empty_push"] += 1
                continue
            pushed_parts = pushed.split(":") if pushed else []
            pushed_swap = sfa.bitmask_swap_impossibility(pushed) or "swappable"
            if args.target_layer_count and len(pushed_parts) != args.target_layer_count:
                rejected["target_layer_count"] += 1
                continue
            if args.target_first_layer and (not pushed_parts or pushed_parts[0] != args.target_first_layer):
                rejected["target_first_layer"] += 1
                continue
            if args.target_top_layer and (not pushed_parts or pushed_parts[-1] != args.target_top_layer):
                rejected["target_top_layer"] += 1
                continue
            if args.target_swap_mode and pushed_swap != args.target_swap_mode:
                rejected["target_swap_mode"] += 1
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
            strict_filter_needed = (
                args.target_strict_verdict != "all"
                or args.exclude_hybrid_targets
                or args.exclude_virtual_corner_targets
            )
            strict = ""
            reason = ""
            if args.target_strict_verdict == "unknown":
                tick = time.perf_counter()
                if sfa.corner_rule_core_verdict(pushed) is not None or sfa.swap_core_verdict(pushed) is not None:
                    timing["cheap_strict_filter"] += time.perf_counter() - tick
                    rejected["target_strict_not_unknown_cheap"] += 1
                    continue
                timing["cheap_strict_filter"] += time.perf_counter() - tick
            if strict_filter_needed:
                tick = time.perf_counter()
                strict, reason = sfa.strict_legacy_verdict_to_symbolic(pushed)
                timing["strict_filter"] += time.perf_counter() - tick
                if args.target_strict_verdict == "known" and strict == "unknown":
                    rejected["target_strict_unknown"] += 1
                    continue
                if args.target_strict_verdict not in {"all", "known"} and strict != args.target_strict_verdict:
                    rejected[f"target_strict_not_{args.target_strict_verdict}"] += 1
                    continue
                if args.exclude_hybrid_targets and "hybrid" in reason:
                    rejected["target_hybrid"] += 1
                    continue
                if args.exclude_virtual_corner_targets and "virtual" in reason:
                    rejected["target_virtual_corner"] += 1
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
            if (
                not args.classify_targets
                and args.write_list_kernel_verdict == "all"
                and not args.write_list_kernel_reason
            ):
                listed_predecessors.add(predecessor)
                listed_targets.add(pushed)
            predecessor_subtypes[predecessor_subtype] += 1
            predecessor_stackability[str(bool(sfa.bitmask_stackability_witnesses(predecessor)))] += 1
            if args.classify_targets:
                if not strict:
                    tick = time.perf_counter()
                    strict, reason = sfa.strict_legacy_verdict_to_symbolic(pushed)
                    timing["strict_classify"] += time.perf_counter() - tick
                target_verdicts[(strict, reason)] += 1
                tick = time.perf_counter()
                relative_tail_candidates = sfa.bitmask_relative_high_tail_inverse_push_pin_candidates(
                    pushed,
                    args.generate_layers,
                )
                timing["relative_tail_probe"] += time.perf_counter() - tick
                if relative_tail_candidates:
                    candidate_source_hits["relative_high_tail"] += 1
                tick = time.perf_counter()
                effective_kernel_verdict = _kernel_verdict_for_target(
                    pushed,
                    args.generate_layers,
                    use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                    predecessor=predecessor,
                )
                timing["kernel_verdict"] += time.perf_counter() - tick
                predecessor_physics = ""
                target_kernel_verdicts[effective_kernel_verdict] += 1
                if (
                    args.audit_fast_terminal_rules
                    and effective_kernel_verdict[1] in FAST_TERMINAL_REASONS
                ):
                    tick = time.perf_counter()
                    slow_kernel_verdict = _kernel_verdict_for_target(
                        pushed,
                        args.generate_layers,
                        use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                        predecessor=predecessor,
                        use_fast_terminal_rules=False,
                    )
                    timing["fast_terminal_audit"] += time.perf_counter() - tick
                    if slow_kernel_verdict[0] != effective_kernel_verdict[0]:
                        fast_terminal_audit_mismatches += 1
                        if len(fast_terminal_audit_samples) < args.max_capture:
                            fast_terminal_audit_samples.append(
                                f"T={pushed}\tfast={effective_kernel_verdict}\tslow={slow_kernel_verdict}"
                            )
                list_verdict_ok = args.write_list_kernel_verdict in {"all", effective_kernel_verdict[0]}
                list_reason_ok = not args.write_list_kernel_reason or effective_kernel_verdict[1] in set(
                    args.write_list_kernel_reason
                )
                if list_verdict_ok and list_reason_ok:
                    listed_predecessors.add(predecessor)
                    listed_targets.add(pushed)
                capture_reasons = set(args.capture_kernel_reason)
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
                        if not predecessor_physics:
                            predecessor_physics = sfa.bitmask_apply_physics(predecessor)
                        unstable_predecessor_candidate_reason = (
                            sfa.claw_unstable_predecessor_candidate_reason(
                                pushed, args.generate_layers
                            )
                        )
                        relative_tail_evidence = sfa.relative_high_tail_evidence(
                            pushed,
                            args.generate_layers,
                        )
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
                                "relative_high_tail_candidate": bool(relative_tail_candidates),
                                "relative_high_tail_evidence": (
                                    {
                                        "predecessor": relative_tail_evidence[0],
                                        "reason": relative_tail_evidence[1],
                                    }
                                    if relative_tail_evidence
                                    else None
                                ),
                                "unstable_predecessor_candidate_reason": unstable_predecessor_candidate_reason,
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
                f"swap={pushed_swap}",
                f"removal={sfa.bitmask_layer_removal_context(pushed)[:3]}",
            )] += 1
        if args.max_raw_tests and tested_raw >= args.max_raw_tests:
            break

    print(f"input={args.data}")
    print(f"train_layers={args.train_layers}")
    print(f"generate_layers={args.generate_layers}")
    print(f"order={args.order}")
    print(f"abstract_mode={args.abstract_mode}")
    print(f"train_subtypes={','.join(args.selected_train_subtypes)}")
    print(f"generate_subtypes={','.join(args.selected_generate_subtypes)}")
    print(f"allow_non_zero_stack_predecessor={args.allow_non_zero_stack_predecessor}")
    print(f"target_strict_verdict={args.target_strict_verdict}")
    print(f"exclude_hybrid_targets={args.exclude_hybrid_targets}")
    print(f"exclude_virtual_corner_targets={args.exclude_virtual_corner_targets}")
    print(f"target_layer_count={args.target_layer_count}")
    print(f"target_first_layer={args.target_first_layer}")
    print(f"target_top_layer={args.target_top_layer}")
    print(f"target_swap_mode={args.target_swap_mode}")
    print(f"records={records}")
    print(f"abstract_ngrams={len(abstract_ngrams)}")
    print(f"abstract_classes={len(raw_by_abstract)}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"tested_raw={tested_raw}")
    print(f"generated_predecessors={len(generated_predecessors)}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print(f"training_cache_hit={training_cache_hit}")
    print(f"training_time={training_time:.6f}s")
    print(f"sequence_time={sequence_time:.6f}s")
    print(f"stop_reason={stop_reason}")
    print(f"raw_truncated={stop_reason != 'exhausted'}")
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
    if timing:
        print("timing:")
        for key, seconds in timing.most_common():
            print(f"  {key}: {seconds:.6f}s")
    if args.classify_targets:
        print("target_verdicts:")
        for key, count in target_verdicts.most_common(args.top):
            print(f"  {key}: {count}")
        print("target_kernel_verdicts:")
        for key, count in target_kernel_verdicts.most_common(args.top):
            print(f"  {key}: {count}")
        if args.audit_fast_terminal_rules:
            print(f"fast_terminal_audit_mismatches={fast_terminal_audit_mismatches}")
            if fast_terminal_audit_samples:
                print("fast_terminal_audit_samples:")
                for sample in fast_terminal_audit_samples:
                    print(sample)
        if KERNEL_STEP_TIMING:
            print("kernel_step_timing:")
            for key, seconds in KERNEL_STEP_TIMING.most_common(args.top):
                count = KERNEL_STEP_COUNTS[key]
                print(f"  {key}: {seconds:.6f}s count={count} avg={seconds / count if count else 0:.9f}s")
        if candidate_source_hits:
            print("candidate_source_hits:")
            for key, count in candidate_source_hits.most_common(args.top):
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
    if args.write_targets:
        args.write_targets.parent.mkdir(parents=True, exist_ok=True)
        args.write_targets.write_text("\n".join(sorted(listed_targets)) + "\n", encoding="utf-8")
        print(f"targets_written={args.write_targets}")
        print(f"targets_written_count={len(listed_targets)}")
    if args.write_predecessors:
        args.write_predecessors.parent.mkdir(parents=True, exist_ok=True)
        args.write_predecessors.write_text("\n".join(sorted(listed_predecessors)) + "\n", encoding="utf-8")
        print(f"predecessors_written={args.write_predecessors}")
        print(f"predecessors_written_count={len(listed_predecessors)}")
    if args.write_summary_json:
        summary = {
            "input": str(args.data),
            "train_layers": args.train_layers,
            "generate_layers": args.generate_layers,
            "order": args.order,
            "abstract_mode": args.abstract_mode,
            "train_subtypes": args.selected_train_subtypes,
            "generate_subtypes": args.selected_generate_subtypes,
            "allow_non_zero_stack_predecessor": args.allow_non_zero_stack_predecessor,
            "target_strict_verdict": args.target_strict_verdict,
            "exclude_hybrid_targets": args.exclude_hybrid_targets,
            "exclude_virtual_corner_targets": args.exclude_virtual_corner_targets,
            "target_layer_count": args.target_layer_count,
            "target_first_layer": args.target_first_layer,
            "target_top_layer": args.target_top_layer,
            "target_swap_mode": args.target_swap_mode,
            "seed": args.seed,
            "records": records,
            "abstract_ngrams": len(abstract_ngrams),
            "abstract_classes": len(raw_by_abstract),
            "abstract_sequences": len(abstract_sequences),
            "abstract_truncated": abstract_truncated,
            "tested_raw": tested_raw,
            "generated_predecessors": len(generated_predecessors),
            "generated_targets": len(generated_targets),
            "training_cache_hit": training_cache_hit,
            "training_time": training_time,
            "sequence_time": sequence_time,
            "listed_predecessors": len(listed_predecessors),
            "listed_targets": len(listed_targets),
            "write_list_kernel_verdict": args.write_list_kernel_verdict,
            "write_list_kernel_reason": list(args.write_list_kernel_reason),
            "stop_reason": stop_reason,
            "raw_truncated": stop_reason != "exhausted",
            "rejected": dict(rejected),
            "target_verdicts": {repr(key): count for key, count in target_verdicts.items()},
            "target_kernel_verdicts": {repr(key): count for key, count in target_kernel_verdicts.items()},
            "candidate_source_hits": dict(candidate_source_hits),
            "predecessor_subtypes": dict(predecessor_subtypes),
            "predecessor_stackability": dict(predecessor_stackability),
            "predecessor_seed_status": dict(predecessor_seed_status),
            "timing": dict(timing),
            "fast_terminal_audit_mismatches": fast_terminal_audit_mismatches,
        }
        args.write_summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"summary_written={args.write_summary_json}")
    if args.classify_targets and args.fail_on_kernel_unknown:
        kernel_unknown = sum(
            count
            for (verdict, _reason), count in target_kernel_verdicts.items()
            if verdict == "unknown"
        )
        print(f"kernel_unknown_failures={kernel_unknown}")
        if kernel_unknown:
            return 1
    if args.classify_targets and args.fail_on_kernel_legacy_fallback:
        kernel_legacy_fallback = sum(
            count
            for (_verdict, reason), count in target_kernel_verdicts.items()
            if reason.startswith("fallback_legacy_core_")
        )
        print(f"kernel_legacy_fallback_failures={kernel_legacy_fallback}")
        if kernel_legacy_fallback:
            return 1
    if args.audit_fast_terminal_rules and args.fail_on_fast_terminal_mismatch and fast_terminal_audit_mismatches:
        return 1
    if args.fail_on_truncated and stop_reason != "exhausted":
        print(f"truncated_failure={stop_reason}")
        return 1
    return 0


def replay_captured(args: argparse.Namespace) -> int:
    counts: Counter[tuple[str, str]] = Counter()
    source_hits: Counter[str] = Counter()
    mismatches: list[str] = []
    unknown_samples: list[str] = []
    source_samples: list[str] = []
    total = 0
    resolved_unknown = 0
    replay_paths = list(args.replay_captured or ())
    for pattern in args.replay_captured_glob:
        replay_paths.extend(sorted(Path().glob(pattern)))
    for replay_path in replay_paths:
        for line in replay_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            target = sfa.normalize_code(str(record["target"]))
            predecessor = sfa.normalize_code(str(record.get("predecessor", "")))
            target_layers = len(target.split(":")) if target else 0
            predecessor_layers = len(predecessor.split(":")) if predecessor else 0
            replay_layers = max(args.generate_layers, target_layers, predecessor_layers)
            expected = (
                str(record.get("kernel_verdict", "")),
                str(record.get("kernel_reason", "")),
            )
            actual = _kernel_verdict_for_target(
                target,
                replay_layers,
                use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                predecessor=predecessor,
            )
            relative_tail_evidence = sfa.relative_high_tail_evidence(target, replay_layers)
            if relative_tail_evidence is not None:
                source_hits["relative_high_tail"] += 1
                if len(source_samples) < args.max_capture:
                    source_samples.append(
                        f"relative_high_tail\tT={target}\tA={relative_tail_evidence[0]}\treason={relative_tail_evidence[1]}"
                    )
            total += 1
            counts[actual] += 1
            if actual[0] == "unknown" and len(unknown_samples) < args.max_capture:
                unknown_samples.append(
                    f"{replay_path}\tT={target}\tA={predecessor}\treason={actual[1]}"
                )
            if expected[0] == "unknown" and actual[0] != "unknown":
                resolved_unknown += 1
            elif expected != actual and len(mismatches) < args.max_capture:
                mismatches.append(
                    f"{replay_path}\tT={target}\texpected={expected[0]}/{expected[1]}\tactual={actual[0]}/{actual[1]}"
                )
    unknown = sum(count for (verdict, _reason), count in counts.items() if verdict == "unknown")
    print(f"replay_captured_count={len(replay_paths)}")
    for replay_path in replay_paths:
        print(f"replay_captured={replay_path}")
    print(f"replay_total={total}")
    print(f"replay_unknown={unknown}")
    print(f"replay_resolved_unknown={resolved_unknown}")
    print("replay_kernel_verdicts:")
    for key, count in counts.most_common(args.top):
        print(f"  {key}: {count}")
    if source_hits:
        print("replay_candidate_source_hits:")
        for key, count in source_hits.most_common(args.top):
            print(f"  {key}: {count}")
    if source_samples:
        print("replay_candidate_source_samples:")
        for sample in source_samples:
            print(sample)
    if mismatches:
        print("replay_mismatches:")
        for mismatch in mismatches:
            print(mismatch)
    if unknown_samples:
        print("replay_unknown_samples:")
        for sample in unknown_samples:
            print(sample)
    if args.fail_on_kernel_unknown and unknown:
        return 1
    if args.fail_on_kernel_legacy_fallback:
        legacy_fallback = sum(
            count
            for (_verdict, reason), count in counts.items()
            if reason.startswith("fallback_legacy_core_")
        )
        print(f"replay_kernel_legacy_fallback={legacy_fallback}")
        if legacy_fallback:
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate exploratory 6-layer claw candidates from abstract half-pair automaton.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--train-layers", type=int, default=5)
    parser.add_argument("--generate-layers", type=int, default=6)
    parser.add_argument("--order", type=int, default=3)
    parser.add_argument("--abstract-mode", choices=("classes", "mask_counts"), default="classes")
    parser.add_argument("--train-subtypes", default="zero_stack", help="zero_stack, all_pp, or comma-separated subtype names.")
    parser.add_argument("--generate-subtypes", default="", help="Defaults to --train-subtypes when omitted.")
    parser.add_argument("--allow-non-zero-stack-predecessor", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-train-seconds", type=float, default=0.0)
    parser.add_argument("--max-abstract-sequences", type=int, default=50000)
    parser.add_argument("--max-raw-per-layer", type=int, default=3)
    parser.add_argument("--max-raw-tests", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--seed-count", type=int, default=1)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--target-claw-common-filter", action="store_true")
    parser.add_argument("--target-sorted-claw-notes-filter", action="store_true")
    parser.add_argument("--target-corner-filter", action="store_true")
    parser.add_argument("--target-swap-both-filter", action="store_true")
    parser.add_argument("--target-removed-crystal-filter", action="store_true")
    parser.add_argument("--target-strict-verdict", choices=("all", "possible", "impossible", "unknown", "known"), default="all")
    parser.add_argument("--exclude-hybrid-targets", action="store_true")
    parser.add_argument("--exclude-virtual-corner-targets", action="store_true")
    parser.add_argument("--target-layer-count", type=int, default=0)
    parser.add_argument("--target-first-layer", default="")
    parser.add_argument("--target-top-layer", default="")
    parser.add_argument("--target-swap-mode", choices=("", "swappable", "swap_12_34_blocked", "swap_14_23_blocked", "swap_both_blocked"), default="")
    parser.add_argument("--require-seed-stackable", action="store_true")
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--classify-targets", action="store_true")
    parser.add_argument("--fail-on-kernel-unknown", action="store_true")
    parser.add_argument("--fail-on-kernel-legacy-fallback", action="store_true")
    parser.add_argument("--fail-on-truncated", action="store_true")
    parser.add_argument("--audit-fast-terminal-rules", action="store_true")
    parser.add_argument("--fail-on-fast-terminal-mismatch", action="store_true")
    parser.add_argument("--disable-legacy-high-tail-candidates", action="store_true")
    parser.add_argument("--disable-high-tail-candidates", action="store_true")
    parser.add_argument("--disable-relative-high-tail-candidates", action="store_true")
    parser.add_argument("--use-generated-predecessor-evidence", action="store_true")
    parser.add_argument("--capture-verdict", action="append", default=[])
    parser.add_argument("--capture-kernel-reason", action="append", default=[])
    parser.add_argument("--max-capture", type=int, default=20)
    parser.add_argument("--max-capture-witnesses", type=int, default=4)
    parser.add_argument("--write-captured", type=Path)
    parser.add_argument("--write-targets", type=Path)
    parser.add_argument("--write-predecessors", type=Path)
    parser.add_argument("--write-list-kernel-verdict", choices=("all", "possible", "impossible", "unknown"), default="all")
    parser.add_argument("--write-list-kernel-reason", action="append", default=[])
    parser.add_argument("--write-summary-json", type=Path)
    parser.add_argument("--training-cache", type=Path, help="Read this cache when valid, otherwise write it after training.")
    parser.add_argument("--read-training-cache", type=Path)
    parser.add_argument("--write-training-cache", type=Path)
    parser.add_argument("--replay-captured", type=Path, action="append", default=[])
    parser.add_argument("--replay-captured-glob", action="append", default=[])
    args = parser.parse_args()
    args.selected_train_subtypes = _selected_subtypes(args.train_subtypes)
    args.selected_generate_subtypes = _selected_subtypes(args.generate_subtypes or args.train_subtypes)
    if args.training_cache is not None:
        if args.read_training_cache is None:
            args.read_training_cache = args.training_cache
        if args.write_training_cache is None:
            args.write_training_cache = args.training_cache
    if args.disable_high_tail_candidates or args.disable_legacy_high_tail_candidates:
        legacy_high_tail = getattr(sfa, "bitmask_high_claw_tail_inverse_push_pin_candidates", None)
        if legacy_high_tail is not None:
            legacy_high_tail.cache_clear()
            sfa.bitmask_high_claw_tail_inverse_push_pin_candidates = lambda code, layers: ()
    if args.disable_relative_high_tail_candidates:
        sfa.bitmask_relative_high_tail_inverse_push_pin_candidates.cache_clear()
        sfa.bitmask_relative_high_tail_inverse_push_pin_candidates = lambda code, layers: ()
    if args.replay_captured or args.replay_captured_glob:
        return replay_captured(args)
    if args.seed_count <= 1:
        return generate(args)
    exit_code = 0
    base_seed = args.seed
    base_write_captured = args.write_captured
    base_write_targets = args.write_targets
    base_write_predecessors = args.write_predecessors
    base_write_summary_json = args.write_summary_json
    pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
    print("shared_training=True")
    print(f"shared_training_cache_hit={training_cache_hit}")
    print(f"shared_training_time={training_time:.6f}s")
    print(f"shared_sequence_time={sequence_time:.6f}s")
    for offset in range(args.seed_count):
        args.seed = base_seed + offset
        if base_write_captured is not None:
            args.write_captured = base_write_captured.with_name(
                f"{base_write_captured.stem}_seed{args.seed}{base_write_captured.suffix}"
            )
        if base_write_targets is not None:
            args.write_targets = base_write_targets.with_name(
                f"{base_write_targets.stem}_seed{args.seed}{base_write_targets.suffix}"
            )
        if base_write_predecessors is not None:
            args.write_predecessors = base_write_predecessors.with_name(
                f"{base_write_predecessors.stem}_seed{args.seed}{base_write_predecessors.suffix}"
            )
        if base_write_summary_json is not None:
            args.write_summary_json = base_write_summary_json.with_name(
                f"{base_write_summary_json.stem}_seed{args.seed}{base_write_summary_json.suffix}"
            )
        print(f"=== seed={args.seed} ===")
        exit_code = max(exit_code, generate(args, pretrained=pretrained))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
