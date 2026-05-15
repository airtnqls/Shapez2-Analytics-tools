from __future__ import annotations

import argparse
import copy
import contextlib
import io
import itertools
import json
import pickle
import random
import sys
import time
from collections import Counter, defaultdict
from functools import lru_cache
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
        "kernel_claw_terminal_connected_pp_predecessor",
        "kernel_claw_terminal_connected_pp_predecessor_rot1",
        "kernel_claw_terminal_connected_pp_predecessor_rot2",
        "kernel_claw_terminal_connected_pp_predecessor_rot3",
        "kernel_claw_terminal_scpp_tail_predecessor",
        "kernel_claw_frontier_tail_invalid_predecessor",
        "kernel_claw_frontier_tail_invalid_predecessor_rot1",
        "kernel_claw_frontier_tail_invalid_predecessor_rot2",
        "kernel_claw_frontier_tail_invalid_predecessor_rot3",
        "kernel_claw_terminal_sss_side_invalid_predecessor",
        "kernel_claw_terminal_sss_side_invalid_predecessor_rot1",
        "kernel_claw_terminal_sss_side_invalid_predecessor_rot2",
        "kernel_claw_terminal_sss_side_invalid_predecessor_rot3",
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
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("metadata")
    expected = _training_cache_metadata(args)
    compatible_full_cache = False
    if isinstance(metadata, dict):
        compatible_full_cache = (
            metadata.get("max_abstract_sequences") == 0
            and {
                key: value
                for key, value in metadata.items()
                if key != "max_abstract_sequences"
            }
            == {
                key: value
                for key, value in expected.items()
                if key != "max_abstract_sequences"
            }
        )
    if metadata != expected and not compatible_full_cache:
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
    abstract_sequences = payload["abstract_sequences"]
    abstract_truncated = payload["abstract_truncated"]
    if compatible_full_cache and args.max_abstract_sequences and len(abstract_sequences) > args.max_abstract_sequences:
        abstract_sequences = abstract_sequences[: args.max_abstract_sequences]
        abstract_truncated = True
    return (
        payload["records"],
        payload["abstract_ngrams"],
        payload["raw_by_abstract"],
        payload["raw_pair_counts"],
        abstract_sequences,
        abstract_truncated,
    )


def _write_training_cache(args: argparse.Namespace, pretrained) -> None:
    if args.write_training_cache is None:
        return
    if args.max_abstract_sequences:
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


def _raw_sequence_choices_for(
    abstract_sequence: tuple[tuple[str, str], ...],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
    max_per_layer: int,
    rng: random.Random,
) -> list[list[tuple[str, str]]]:
    choices: list[list[tuple[str, str]]] = []
    for abstract in abstract_sequence:
        raw = sorted(raw_by_abstract.get(abstract, ()), key=lambda item: (-raw_pair_counts[item], item))
        if not raw:
            return []
        if max_per_layer and len(raw) > max_per_layer:
            head = raw[:max_per_layer]
            if len(raw) > max_per_layer * 2:
                raw = head + rng.sample(raw[max_per_layer:], max_per_layer)
            else:
                raw = head
        choices.append(raw)
    return choices


def _iter_raw_sequences_for(
    abstract_sequence: tuple[tuple[str, str], ...],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
    max_per_layer: int,
    rng: random.Random,
):
    choices = _raw_sequence_choices_for(abstract_sequence, raw_by_abstract, raw_pair_counts, max_per_layer, rng)
    if not choices:
        return
    yielded = 0
    for raw_sequence in itertools.product(*choices):
        yield raw_sequence
        yielded += 1
        if yielded >= 100_000:
            return


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
    cheap_prune_only: bool = False,
) -> tuple[str, str]:
    strict_verdict: tuple[str, str] | None = None
    kernel_verdict = sfa.corner_rule_core_verdict(target)
    if kernel_verdict is None:
        kernel_verdict = sfa.swap_core_verdict(target)
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
            kernel_verdict = sfa.claw_terminal_connected_pp_predecessor_core_verdict(target, layers)
            if kernel_verdict is not None:
                return kernel_verdict
            if sfa.claw_terminal_scpp_tail_predecessor_witness(target, layers) is not None:
                return "possible", "kernel_claw_terminal_scpp_tail_predecessor"
            kernel_verdict = sfa.claw_terminal_sss_side_invalid_predecessor_core_verdict(target, layers)
            if kernel_verdict is not None:
                return kernel_verdict
            kernel_verdict = sfa.claw_frontier_tail_invalid_predecessor_core_verdict(target, layers)
            if kernel_verdict is not None:
                return kernel_verdict
            if use_generated_predecessor_evidence and predecessor:
                predecessor = sfa.normalize_code(predecessor)
                predecessor_physics = sfa.bitmask_apply_physics(predecessor)
                terminal_pp_verdict = sfa.zero_stack_terminal_crystal_pp_predecessor_core_verdict(target, layers)
                if terminal_pp_verdict is not None:
                    return terminal_pp_verdict
                if (
                    predecessor_physics != predecessor
                    and sfa.bitmask_push_pin(predecessor, layers) == sfa.normalize_code(target)
                ):
                    return "impossible", "kernel_generated_predecessor_unstable_after_terminal_probe"
        if cheap_prune_only:
            return "unknown", "kernel_residual_after_fast_prune"
        for kernel_fn in (
            sfa.swap_core_verdict,
            sfa.zero_stack_terminal_crystal_pp_predecessor_core_verdict,
            sfa.zero_stack_terminal_crystal_failure_core_verdict,
            sfa.generic_viable_pin_push_predecessor_core_verdict,
            sfa.claw_unstable_predecessor_core_verdict,
            sfa.claw_change_rule_predecessor_core_verdict,
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
    if kernel_verdict is not None:
        return kernel_verdict
    if strict_verdict is None:
        strict_verdict = sfa.strict_legacy_verdict_to_symbolic(target)
    return strict_verdict


def _predecessor_feature(code: str):
    parts = code.split(":") if code else []
    return (
        f"layers={len(parts)}",
        f"top={parts[-1] if parts else '----'}",
        f"swap={sfa.bitmask_swap_impossibility(code) or 'swappable'}",
    )


def _target_feature(code: str, swap_mode: str | None = None):
    parts = code.split(":") if code else []
    return (
        f"layers={len(parts)}",
        f"first={parts[0] if parts else '----'}",
        f"top={parts[-1] if parts else '----'}",
        f"swap={swap_mode or sfa.bitmask_swap_impossibility(code) or 'swappable'}",
        f"removal={sfa.bitmask_layer_removal_context(code)[:3]}",
    )


@lru_cache(maxsize=300_000)
def _canonical_frontier_signature(code: str, mode: str = "exact") -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return ""
    variants: list[str] = []
    for flipped in (False, True):
        source = sfa._flip_code_text(normalized) if flipped else normalized
        for turns in range(4):
            variant = sfa.normalize_code(sfa._rotate_code_text(source, turns))
            if mode != "exact":
                variant = ":".join(_abstract_layer(layer, mode) for layer in variant.split(":"))
            variants.append(variant)
    return min(variant for variant in variants if variant)


def _frontier_layer_drop_projections(code: str, base_layers: int) -> tuple[tuple[str, str], ...]:
    normalized = sfa.normalize_code(code)
    parts = normalized.split(":") if normalized else []
    projections: list[tuple[str, str]] = []
    if len(parts) == base_layers:
        projections.append(("same_depth", normalized))
    if len(parts) <= base_layers:
        return tuple(projections)
    top_removed, _removed = sfa.bitmask_remove_top_nonempty_layer(normalized)
    if len(top_removed.split(":")) == base_layers:
        projections.append(("remove_top_nonempty", top_removed))
    if len(parts) - 1 == base_layers:
        projections.append(("remove_bottom_layer", sfa.normalize_code(":".join(parts[1:]))))
        for index in range(len(parts)):
            projected = sfa.normalize_code(":".join(parts[:index] + parts[index + 1 :]))
            projections.append((f"remove_layer_{index}", projected))
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for reason, projected in projections:
        key = f"{reason}\t{projected}"
        if projected and key not in seen:
            seen.add(key)
            unique.append((reason, projected))
    return tuple(unique)


def _load_frontier_base_signatures(data: Path, base_layers: int, mode: str) -> set[str]:
    signatures: set[str] = set()
    for code in sfa.iter_data_codes(data, max_layers=base_layers):
        normalized = sfa.normalize_code(code)
        if len(normalized.split(":")) != base_layers:
            continue
        signatures.add(_canonical_frontier_signature(normalized, mode))
    return signatures


def _frontier_projection_reason(
    code: str,
    *,
    base_layers: int,
    base_signatures: set[str],
    signature_mode: str,
) -> tuple[str, str]:
    for reason, projected in _frontier_layer_drop_projections(code, base_layers):
        signature = _canonical_frontier_signature(projected, signature_mode)
        if signature in base_signatures:
            return "derived", reason
    return "new", "no_base_projection"


def _predecessor_frontier_projection_reason(
    predecessor: str,
    *,
    base_signatures: set[str],
    signature_mode: str,
) -> tuple[str, str]:
    normalized = sfa.normalize_code(predecessor)
    parts = normalized.split(":") if normalized else []
    projections: list[tuple[str, str]] = [("same_pre_depth", normalized)]
    if len(parts) > 1:
        top_removed, _removed = sfa.bitmask_remove_top_nonempty_layer(normalized)
        projections.append(("pre_remove_top_nonempty", top_removed))
        projections.append(("pre_remove_bottom_layer", sfa.normalize_code(":".join(parts[1:]))))
        for index in range(len(parts)):
            projections.append((f"pre_remove_layer_{index}", sfa.normalize_code(":".join(parts[:index] + parts[index + 1 :]))))
    physics = sfa.bitmask_apply_physics(normalized)
    if physics != normalized:
        projections.append(("pre_physics", physics))
    for reason, projected in projections:
        signature = _canonical_frontier_signature(projected, signature_mode)
        if signature in base_signatures:
            return "derived", reason
    return "new", "no_pre_projection"


def estimate_generation_space(args: argparse.Namespace, pretrained=None) -> int:
    started = time.perf_counter()
    if pretrained is None:
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
    else:
        training_time = 0.0
        sequence_time = 0.0
        training_cache_hit = False
    records, _abstract_ngrams, raw_by_abstract, _raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    products: list[int] = []
    missing = 0
    for abstract_sequence in abstract_sequences:
        product = 1
        for abstract in abstract_sequence:
            count = len(raw_by_abstract.get(abstract, ()))
            if not count:
                missing += 1
                product = 0
                break
            if args.max_raw_per_layer:
                count = min(count, args.max_raw_per_layer * 2)
            product *= count
        products.append(product)
    raw_choice_sizes = sorted((len(raw) for raw in raw_by_abstract.values()), reverse=True)
    capped_sum = sum(min(product, 10**18) for product in products)
    print("mode=estimate_generation_space")
    print(f"records={records}")
    print(f"abstract_classes={len(raw_by_abstract)}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"missing_sequences={missing}")
    print(f"raw_choice_max={raw_choice_sizes[0] if raw_choice_sizes else 0}")
    print(f"raw_choice_top10={raw_choice_sizes[:10]}")
    print(f"raw_product_top10={sorted(products, reverse=True)[:10]}")
    print(f"raw_product_sum_capped_1e18={capped_sum}")
    print(f"raw_product_le_1={sum(1 for product in products if product <= 1)}")
    print(f"raw_product_le_100={sum(1 for product in products if product <= 100)}")
    print(f"raw_product_gt_100k={sum(1 for product in products if product > 100_000)}")
    print(f"training_cache_hit={training_cache_hit}")
    print(f"training_time={training_time:.6f}s")
    print(f"sequence_time={sequence_time:.6f}s")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    return 0


def sample_pp_essential_profile(args: argparse.Namespace, pretrained=None) -> int:
    started = time.perf_counter()
    rng = random.Random(args.seed)
    if pretrained is None:
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
    else:
        training_time = 0.0
        sequence_time = 0.0
        training_cache_hit = False
    records, _abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    if args.shuffle:
        rng.shuffle(abstract_sequences)
    tested_raw = 0
    unique_predecessors: set[str] = set()
    unique_targets: set[str] = set()
    pre_profile = Counter()
    target_profile = Counter()
    stackable_predecessors = 0
    stackable_predecessor_push_targets: set[str] = set()
    stop_reason = "exhausted"
    for abstract_sequence in abstract_sequences:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            stop_reason = "max_seconds"
            break
        raw_sequences = _iter_raw_sequences_for(
            abstract_sequence,
            raw_by_abstract,
            raw_pair_counts,
            args.max_raw_per_layer,
            rng,
        )
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
                pre_profile["overlap"] += 1
                continue
            subtype = sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype
            if subtype not in args.selected_generate_subtypes:
                pre_profile["subtype_rejected"] += 1
                continue
            parts = predecessor.split(":")
            top = parts[-1] if parts else "----"
            has_top_crystal = "c" in top
            has_top_content = any(ch != "-" for ch in top)
            stackable = bool(sfa.bitmask_stackability_witnesses(predecessor))
            if args.exclude_stackable_predecessors and stackable:
                pre_profile["stackable_predecessor"] += 1
                continue
            pushed = sfa.bitmask_push_pin(predecessor, args.generate_layers)
            if not pushed:
                pre_profile["empty_push"] += 1
                continue
            unique_predecessors.add(predecessor)
            unique_targets.add(pushed)
            if stackable:
                stackable_predecessors += 1
                stackable_predecessor_push_targets.add(pushed)
            pre_profile[
                (
                    f"subtype={subtype}",
                    f"stackable={int(stackable)}",
                    f"top_crystal={int(has_top_crystal)}",
                    f"top_content={int(has_top_content)}",
                    f"swap={sfa.bitmask_swap_impossibility(predecessor) or 'swappable'}",
                )
            ] += 1
            target_profile[_target_feature(pushed)] += 1
        if stop_reason != "exhausted":
            break
    print("mode=pp_essential_profile")
    print(f"records={records}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"tested_raw={tested_raw}")
    print(f"unique_predecessors={len(unique_predecessors)}")
    print(f"unique_targets={len(unique_targets)}")
    print(f"stackable_predecessors={stackable_predecessors}")
    print(f"stackable_predecessor_unique_push_targets={len(stackable_predecessor_push_targets)}")
    print(f"training_cache_hit={training_cache_hit}")
    print(f"training_time={training_time:.6f}s")
    print(f"sequence_time={sequence_time:.6f}s")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print(f"stop_reason={stop_reason}")
    print("predecessor_profile:")
    for key, count in pre_profile.most_common(args.top):
        print(f"  {count}\t{key}")
    print("target_profile:")
    for key, count in target_profile.most_common(args.top):
        print(f"  {count}\t{key}")
    return 0


def frontier_signature_profile(args: argparse.Namespace, pretrained=None) -> int:
    started = time.perf_counter()
    rng = random.Random(args.seed)
    base_layers = args.frontier_base_layers or args.train_layers
    base_signatures = _load_frontier_base_signatures(args.data, base_layers, args.frontier_signature_mode)
    if pretrained is None:
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
    else:
        training_time = 0.0
        sequence_time = 0.0
        training_cache_hit = False
    records, _abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    if args.shuffle:
        rng.shuffle(abstract_sequences)
    tested_raw = 0
    generated_targets: set[str] = set()
    frontier_counts = Counter()
    frontier_features = Counter()
    new_samples: list[str] = []
    stop_reason = "exhausted"
    for abstract_sequence in abstract_sequences:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            stop_reason = "max_seconds"
            break
        raw_sequences = _iter_raw_sequences_for(
            abstract_sequence,
            raw_by_abstract,
            raw_pair_counts,
            args.max_raw_per_layer,
            rng,
        )
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
                frontier_counts[("rejected", "overlap")] += 1
                continue
            subtype = sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype
            if subtype not in args.selected_generate_subtypes:
                frontier_counts[("rejected", "subtype")] += 1
                continue
            if args.exclude_stackable_predecessors and sfa.bitmask_stackability_witnesses(predecessor):
                frontier_counts[("rejected", "stackable_predecessor")] += 1
                continue
            pushed = sfa.bitmask_push_pin(predecessor, args.generate_layers)
            if not pushed:
                frontier_counts[("rejected", "empty_push")] += 1
                continue
            if args.dedupe_targets_before_classify and pushed in generated_targets:
                frontier_counts[("rejected", "duplicate_target")] += 1
                continue
            generated_targets.add(pushed)
            status, reason = _frontier_projection_reason(
                pushed,
                base_layers=base_layers,
                base_signatures=base_signatures,
                signature_mode=args.frontier_signature_mode,
            )
            frontier_counts[(status, reason)] += 1
            if status == "new":
                frontier_features[_target_feature(pushed)] += 1
                if len(new_samples) < args.max_capture:
                    new_samples.append(pushed)
        if stop_reason != "exhausted":
            break
    print("mode=frontier_signature_profile")
    print(f"signature_mode={args.frontier_signature_mode}")
    print(f"base_layers={base_layers}")
    print(f"base_signatures={len(base_signatures)}")
    print(f"generate_layers={args.generate_layers}")
    print(f"records={records}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"tested_raw={tested_raw}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"training_cache_hit={training_cache_hit}")
    print(f"training_time={training_time:.6f}s")
    print(f"sequence_time={sequence_time:.6f}s")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print(f"stop_reason={stop_reason}")
    print("frontier_counts:")
    for key, count in frontier_counts.most_common(args.top):
        print(f"  {count}\t{key}")
    if frontier_features:
        print("new_frontier_features:")
        for key, count in frontier_features.most_common(args.top):
            print(f"  {count}\t{key}")
    if new_samples:
        print("new_frontier_samples:")
        for sample in new_samples:
            print(sample)
    return 0


def frontier_data_profile(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    base_layers = args.frontier_base_layers or args.train_layers
    target_layers = args.generate_layers
    base_signatures = _load_frontier_base_signatures(args.data, base_layers, args.frontier_signature_mode)
    counts = Counter()
    features = Counter()
    samples: list[str] = []
    checked = 0
    for code in sfa.iter_data_codes(args.data, max_layers=target_layers):
        normalized = sfa.normalize_code(code)
        if not normalized or len(normalized.split(":")) != target_layers:
            continue
        checked += 1
        status, reason = _frontier_projection_reason(
            normalized,
            base_layers=base_layers,
            base_signatures=base_signatures,
            signature_mode=args.frontier_signature_mode,
        )
        counts[(status, reason)] += 1
        if status == "new":
            features[_target_feature(normalized)] += 1
            if len(samples) < args.max_capture:
                samples.append(normalized)
    print("mode=frontier_data_profile")
    print(f"signature_mode={args.frontier_signature_mode}")
    print(f"base_layers={base_layers}")
    print(f"target_layers={target_layers}")
    print(f"base_signatures={len(base_signatures)}")
    print(f"checked={checked}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("frontier_counts:")
    for key, count in counts.most_common(args.top):
        print(f"  {count}\t{key}")
    if features:
        print("new_frontier_features:")
        for key, count in features.most_common(args.top):
            print(f"  {count}\t{key}")
    if samples:
        print("new_frontier_samples:")
        for sample in samples:
            print(sample)
    return 0


def predecessor_frontier_data_profile(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    base_layers = args.frontier_base_layers or args.train_layers
    target_layers = args.generate_layers
    base_signatures: set[str] = set()
    base_checked = 0
    for code in sfa.iter_data_codes(args.data, max_layers=base_layers):
        target = sfa.normalize_code(code)
        if not target or len(target.split(":")) != base_layers:
            continue
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, base_layers) != target:
            continue
        base_checked += 1
        base_signatures.add(_canonical_frontier_signature(predecessor, args.frontier_signature_mode))
    counts = Counter()
    features = Counter()
    samples: list[str] = []
    checked = 0
    valid_predecessors = 0
    for code in sfa.iter_data_codes(args.data, max_layers=target_layers):
        target = sfa.normalize_code(code)
        if not target or len(target.split(":")) != target_layers:
            continue
        checked += 1
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, target_layers) != target:
            counts[("rejected", "predecessor_push_mismatch")] += 1
            continue
        valid_predecessors += 1
        status, reason = _predecessor_frontier_projection_reason(
            predecessor,
            base_signatures=base_signatures,
            signature_mode=args.frontier_signature_mode,
        )
        counts[(status, reason)] += 1
        if status == "new":
            features[_target_feature(target)] += 1
            if len(samples) < args.max_capture:
                samples.append(f"T={target}\tP={predecessor}")
    print("mode=predecessor_frontier_data_profile")
    print(f"signature_mode={args.frontier_signature_mode}")
    print(f"base_layers={base_layers}")
    print(f"target_layers={target_layers}")
    print(f"base_checked={base_checked}")
    print(f"base_predecessor_signatures={len(base_signatures)}")
    print(f"checked={checked}")
    print(f"valid_predecessors={valid_predecessors}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("frontier_counts:")
    for key, count in counts.most_common(args.top):
        print(f"  {count}\t{key}")
    if features:
        print("new_frontier_features:")
        for key, count in features.most_common(args.top):
            print(f"  {count}\t{key}")
    if samples:
        print("new_frontier_samples:")
        for sample in samples:
            print(sample)
    return 0


def _bucket_count(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    if value <= 4:
        return "3-4"
    return "5+"


def _relative_depth_bucket(depth: int) -> str:
    if depth >= 0:
        return "overflow"
    if depth == -1:
        return "-1"
    if depth == -2:
        return "-2"
    if depth == -3:
        return "-3"
    return "<=-4"


def _predecessor_push_event(predecessor: str, layers: int) -> tuple[list[tuple[int, int]], int, bool]:
    source_layers = [list(layer) for layer in sfa.normalize_code(predecessor).split(":")]
    pin_layer = ["P" if ch != "-" else "-" for ch in source_layers[0]]
    shifted_layers = [pin_layer] + [layer[:] for layer in source_layers]
    initial_destroyed = {
        (layer_index, quadrant)
        for layer_index in range(layers, len(shifted_layers))
        for quadrant in range(4)
        if sfa._piece_at(shifted_layers, layer_index, quadrant) != "-"
    }
    shattered = sfa._shatter_set(shifted_layers, initial_destroyed)
    crystal_coords = [
        (layer_index - layers, quadrant)
        for layer_index, quadrant in shattered
        if sfa._piece_at(shifted_layers, layer_index, quadrant) == "c"
    ]
    non_crystal_count = sum(
        1
        for layer_index, quadrant in shattered
        if sfa._piece_at(shifted_layers, layer_index, quadrant) not in ("-", "c")
    )
    raw_layers = [layer[:] for layer in shifted_layers]
    for layer_index, quadrant in shattered:
        if 0 <= layer_index < len(raw_layers):
            raw_layers[layer_index][quadrant] = "-"
    raw_code = sfa.normalize_code(":".join("".join(layer) for layer in raw_layers[:layers]))
    falls_after_shatter = raw_code != sfa.bitmask_apply_physics(raw_code)
    return crystal_coords, non_crystal_count, falls_after_shatter


def _predecessor_push_family(predecessor: str, target: str) -> tuple[object, ...]:
    layers = len(target.split(":"))
    crystal_coords, non_crystal_count, falls_after_shatter = _predecessor_push_event(predecessor, layers)
    by_quadrant: defaultdict[int, list[int]] = defaultdict(list)
    for relative_depth, quadrant in crystal_coords:
        by_quadrant[quadrant].append(relative_depth)
    spans: list[tuple[int, int, int, int, int]] = []
    for quadrant, depths in by_quadrant.items():
        spans.append((len(depths), max(depths) - min(depths) + 1, min(depths), max(depths), quadrant))
    spans.sort(reverse=True)
    if spans:
        main = (
            "main",
            _bucket_count(spans[0][0]),
            _bucket_count(spans[0][1]),
            _relative_depth_bucket(spans[0][2]),
            _relative_depth_bucket(spans[0][3]),
        )
    else:
        main = ("main", "0", "0", "none", "none")
    below_cols = sum(1 for depths in by_quadrant.values() if any(depth < 0 for depth in depths))
    overflow_cols = sum(1 for depths in by_quadrant.values() if any(depth >= 0 for depth in depths))
    side_cols = max(0, len(by_quadrant) - 1)
    return (
        "cols_" + _bucket_count(len(by_quadrant)),
        "below_cols_" + _bucket_count(below_cols),
        "overflow_cols_" + _bucket_count(overflow_cols),
        "side_" + _bucket_count(side_cols),
        main,
        "nonc_" + _bucket_count(non_crystal_count),
        "falls" if falls_after_shatter else "no_fall",
    )


def _predecessor_push_exact_family(predecessor: str, target: str) -> tuple[object, ...]:
    layers = len(target.split(":"))
    crystal_coords, non_crystal_count, falls_after_shatter = _predecessor_push_event(predecessor, layers)
    rotated_variants = []
    for turns in range(4):
        rotated_variants.append(tuple(sorted((relative_depth, (quadrant + turns) % 4) for relative_depth, quadrant in crystal_coords)))
    return (
        "exact",
        min(rotated_variants) if rotated_variants else (),
        "nonc",
        non_crystal_count,
        "falls" if falls_after_shatter else "no_fall",
    )


def _predecessor_push_signature(predecessor: str, target: str, mode: str) -> tuple[object, ...]:
    if mode == "exact":
        return _predecessor_push_exact_family(predecessor, target)
    return _predecessor_push_family(predecessor, target)


def predecessor_family_data_profile(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    max_layers = args.generate_layers
    layer_families: defaultdict[int, Counter[tuple[object, ...]]] = defaultdict(Counter)
    examples: defaultdict[int, dict[tuple[object, ...], tuple[str, str]]] = defaultdict(dict)
    checked = Counter()
    valid = Counter()
    rejected = Counter()
    for code in sfa.iter_data_codes(args.data, max_layers=max_layers):
        target = sfa.normalize_code(code)
        if not target:
            continue
        layers = len(target.split(":"))
        if layers > max_layers:
            continue
        checked[layers] += 1
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, layers) != target:
            rejected[layers] += 1
            continue
        valid[layers] += 1
        family = _predecessor_push_signature(predecessor, target, args.predecessor_family_mode)
        layer_families[layers][family] += 1
        examples[layers].setdefault(family, (target, predecessor))
    print("mode=predecessor_family_data_profile")
    print(f"family_mode={args.predecessor_family_mode}")
    print(f"max_layers={max_layers}")
    print(f"checked_by_layer={dict(sorted(checked.items()))}")
    print(f"valid_by_layer={dict(sorted(valid.items()))}")
    print(f"rejected_by_layer={dict(sorted(rejected.items()))}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    previous_families: set[tuple[object, ...]] = set()
    for layers in sorted(layer_families):
        families = layer_families[layers]
        new_families = set(families) - previous_families
        print(
            f"layer={layers} total={sum(families.values())} "
            f"families={len(families)} new_vs_lower={len(new_families)}"
        )
        for family, count in families.most_common(args.top):
            marker = "new" if family in new_families else "old"
            print(f"  {count}\t{marker}\t{family}")
        captured = 0
        for family in sorted(new_families, key=str):
            if captured >= args.max_capture:
                break
            target, predecessor = examples[layers][family]
            print(f"  sample\tfamily={family}\tT={target}\tP={predecessor}")
            captured += 1
        previous_families.update(families)
    return 0


def _load_predecessor_families(data: Path, layers: int, mode: str) -> set[tuple[object, ...]]:
    families: set[tuple[object, ...]] = set()
    for code in sfa.iter_data_codes(data, max_layers=layers):
        target = sfa.normalize_code(code)
        if not target or len(target.split(":")) != layers:
            continue
        predecessor = _claw_predecessor(target)
        if not predecessor or sfa.bitmask_push_pin(predecessor, layers) != target:
            continue
        families.add(_predecessor_push_signature(predecessor, target, mode))
    return families


def predecessor_new_family_candidates(args: argparse.Namespace, pretrained=None) -> int:
    started = time.perf_counter()
    rng = random.Random(args.seed)
    base_layers = args.frontier_base_layers or args.train_layers
    base_families = _load_predecessor_families(args.data, base_layers, args.predecessor_family_mode)
    if pretrained is None:
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
    else:
        training_time = 0.0
        sequence_time = 0.0
        training_cache_hit = False
    records, _abstract_ngrams, raw_by_abstract, raw_pair_counts, abstract_sequences, abstract_truncated = pretrained
    if args.shuffle:
        rng.shuffle(abstract_sequences)

    tested_raw = 0
    generated_targets: set[str] = set()
    generated_predecessors: set[str] = set()
    new_targets: set[str] = set()
    new_pairs: set[tuple[str, str]] = set()
    family_counts = Counter()
    new_family_counts = Counter()
    new_family_verdicts = Counter()
    rejected = Counter()
    new_samples: list[str] = []
    stop_reason = "exhausted"
    for abstract_sequence in abstract_sequences:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            stop_reason = "max_seconds"
            break
        raw_sequences = _iter_raw_sequences_for(
            abstract_sequence,
            raw_by_abstract,
            raw_pair_counts,
            args.max_raw_per_layer,
            rng,
        )
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
            if args.dedupe_predecessors_before_push and predecessor in generated_predecessors:
                rejected["duplicate_predecessor"] += 1
                continue
            generated_predecessors.add(predecessor)
            subtype = sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype
            if subtype not in args.selected_generate_subtypes:
                rejected["subtype"] += 1
                continue
            if args.exclude_stackable_predecessors and sfa.bitmask_stackability_witnesses(predecessor):
                rejected["stackable_predecessor"] += 1
                continue
            if not args.allow_non_zero_stack_predecessor and not sfa.top_single_c_zero_stack_candidate(predecessor):
                rejected["not_zero_stack"] += 1
                continue
            pushed = sfa.bitmask_push_pin(predecessor, args.generate_layers)
            if not pushed:
                rejected["empty_push"] += 1
                continue
            pushed_parts = pushed.split(":") if pushed else []
            if args.target_layer_count and len(pushed_parts) != args.target_layer_count:
                rejected["target_layer_count"] += 1
                continue
            if args.dedupe_targets_before_classify and pushed in generated_targets:
                rejected["duplicate_target"] += 1
                continue
            generated_targets.add(pushed)
            family = _predecessor_push_signature(predecessor, pushed, args.predecessor_family_mode)
            family_counts[family] += 1
            if family in base_families:
                continue
            new_family_counts[family] += 1
            new_targets.add(pushed)
            new_pairs.add((pushed, predecessor))
            if args.classify_new_family_candidates:
                verdict = _kernel_verdict_for_target(
                    pushed,
                    args.generate_layers,
                    use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                    predecessor=predecessor,
                    cheap_prune_only=args.cheap_prune_only,
                )
                if verdict[0] == "unknown" and args.classify_residual_full:
                    verdict = _kernel_verdict_for_target(
                        pushed,
                        args.generate_layers,
                        use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                        predecessor=predecessor,
                        cheap_prune_only=False,
                    )
                new_family_verdicts[verdict] += 1
            if len(new_samples) < args.max_capture:
                new_samples.append(f"family={family}\tT={pushed}\tA={predecessor}")
        if stop_reason != "exhausted":
            break

    print("mode=predecessor_new_family_candidates")
    print(f"family_mode={args.predecessor_family_mode}")
    print(f"base_layers={base_layers}")
    print(f"base_families={len(base_families)}")
    print(f"generate_layers={args.generate_layers}")
    print(f"records={records}")
    print(f"abstract_sequences={len(abstract_sequences)}")
    print(f"abstract_truncated={abstract_truncated}")
    print(f"tested_raw={tested_raw}")
    print(f"generated_predecessors={len(generated_predecessors)}")
    print(f"generated_targets={len(generated_targets)}")
    print(f"new_family_count={len(new_family_counts)}")
    print(f"new_targets={len(new_targets)}")
    print(f"training_cache_hit={training_cache_hit}")
    print(f"training_time={training_time:.6f}s")
    print(f"sequence_time={sequence_time:.6f}s")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print(f"stop_reason={stop_reason}")
    print("rejected:")
    for key, count in rejected.most_common(args.top):
        print(f"  {key}: {count}")
    print("all_families:")
    for key, count in family_counts.most_common(args.top):
        marker = "new" if key in new_family_counts else "old"
        print(f"  {count}\t{marker}\t{key}")
    print("new_families:")
    for key, count in new_family_counts.most_common(args.top):
        print(f"  {count}\t{key}")
    if args.classify_new_family_candidates:
        print("new_family_kernel_verdicts:")
        for key, count in new_family_verdicts.most_common(args.top):
            print(f"  {count}\t{key}")
    if new_samples:
        print("new_family_samples:")
        for sample in new_samples:
            print(sample)
    if args.write_targets:
        args.write_targets.parent.mkdir(parents=True, exist_ok=True)
        args.write_targets.write_text("\n".join(sorted(new_targets)) + "\n", encoding="utf-8")
        print(f"new_family_targets_written={args.write_targets}")
        print(f"new_family_targets_written_count={len(new_targets)}")
    if args.write_pairs:
        args.write_pairs.parent.mkdir(parents=True, exist_ok=True)
        args.write_pairs.write_text(
            "\n".join(f"{target}\t{predecessor}" for target, predecessor in sorted(new_pairs)) + "\n",
            encoding="utf-8",
        )
        print(f"new_family_pairs_written={args.write_pairs}")
        print(f"new_family_pairs_written_count={len(new_pairs)}")
    if args.classify_new_family_candidates and args.fail_on_kernel_unknown:
        unknown = sum(count for (verdict, _reason), count in new_family_verdicts.items() if verdict == "unknown")
        print(f"new_family_kernel_unknown_failures={unknown}")
        if unknown:
            return 1
    if args.classify_new_family_candidates and args.fail_on_kernel_legacy_fallback:
        legacy_fallback = sum(
            count for (_verdict, reason), count in new_family_verdicts.items() if reason.startswith("fallback_legacy_core_")
        )
        print(f"new_family_kernel_legacy_fallback_failures={legacy_fallback}")
        if legacy_fallback:
            return 1
    return 0


def high_layer_pp_smoke(args: argparse.Namespace) -> int:
    exit_code = 0
    layers = [int(part.strip()) for part in args.high_layer_pp_smoke.split(",") if part.strip()]
    for index, layers_value in enumerate(layers):
        smoke_args = copy.copy(args)
        smoke_args.generate_layers = layers_value
        smoke_args.seed = args.seed + index
        smoke_args.max_abstract_sequences = args.smoke_abstract_sequences
        smoke_args.max_raw_tests = args.smoke_raw_tests
        smoke_args.classify_targets = True
        smoke_args.kernel_only_classify = True
        smoke_args.dedupe_targets_before_classify = True
        smoke_args.cheap_prune_only = True
        smoke_args.classify_residual_full = True
        smoke_args.skip_predecessor_details = True
        smoke_args.use_generated_predecessor_evidence = True
        smoke_args.fail_on_kernel_unknown = True
        smoke_args.fail_on_kernel_legacy_fallback = True
        smoke_args.write_captured = None
        smoke_args.write_targets = None
        smoke_args.write_predecessors = None
        smoke_args.write_pairs = None
        smoke_args.write_summary_json = None
        smoke_args.read_training_cache = None
        smoke_args.write_training_cache = None
        smoke_args.training_cache = None
        print(f"=== high_layer_pp_smoke layers={layers_value} seed={smoke_args.seed} ===")
        exit_code = max(exit_code, generate(smoke_args))
    return exit_code


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
    seen_predecessors_before_push: set[str] = set()
    generated_predecessors: set[str] = set()
    generated_targets: set[str] = set()
    seen_targets_for_classification: set[str] = set()
    listed_predecessors: set[str] = set()
    listed_targets: set[str] = set()
    listed_pairs: set[tuple[str, str]] = set()
    rejected = Counter()
    target_features = Counter()
    residual_target_features = Counter()
    residual_predecessor_features = Counter()
    predecessor_push_families = Counter()
    residual_predecessor_push_families = Counter()
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
        raw_sequences = _iter_raw_sequences_for(
            abstract_sequence,
            raw_by_abstract,
            raw_pair_counts,
            args.max_raw_per_layer,
            rng,
        )
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
            if args.dedupe_predecessors_before_push:
                if predecessor in seen_predecessors_before_push:
                    rejected["duplicate_predecessor_before_push"] += 1
                    continue
                seen_predecessors_before_push.add(predecessor)
            predecessor_subtype = sfa.pp_subtype_candidate(predecessor, args.generate_layers).subtype
            if predecessor_subtype not in args.selected_generate_subtypes:
                rejected["subtype"] += 1
                continue
            if args.exclude_stackable_predecessors and sfa.bitmask_stackability_witnesses(predecessor):
                rejected["stackable_predecessor"] += 1
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
            if args.dedupe_targets_before_classify and pushed in seen_targets_for_classification:
                rejected["duplicate_target_before_classify"] += 1
                continue
            seen_targets_for_classification.add(pushed)
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
            if not args.skip_predecessor_details or args.require_seed_stackable:
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
            predecessor_push_family = None
            if args.predecessor_family_summary:
                predecessor_push_family = _predecessor_push_family(predecessor, pushed)
                predecessor_push_families[predecessor_push_family] += 1
            if (
                not args.classify_targets
                and args.write_list_kernel_verdict == "all"
                and not args.write_list_kernel_reason
            ):
                listed_predecessors.add(predecessor)
                listed_targets.add(pushed)
                listed_pairs.add((pushed, predecessor))
            predecessor_subtypes[predecessor_subtype] += 1
            if not args.skip_predecessor_details:
                predecessor_stackability[str(bool(sfa.bitmask_stackability_witnesses(predecessor)))] += 1
            if args.classify_targets:
                if args.kernel_only_classify and not strict_filter_needed:
                    strict, reason = "skipped", "strict_classify_skipped"
                elif not strict:
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
                    cheap_prune_only=args.cheap_prune_only,
                )
                timing["kernel_verdict"] += time.perf_counter() - tick
                if effective_kernel_verdict[0] == "unknown":
                    residual_target_features[_target_feature(pushed, pushed_swap)] += 1
                    residual_predecessor_features[_predecessor_feature(predecessor)] += 1
                    if args.predecessor_family_summary:
                        residual_predecessor_push_families[
                            predecessor_push_family or _predecessor_push_family(predecessor, pushed)
                        ] += 1
                    if args.classify_residual_full:
                        tick = time.perf_counter()
                        effective_kernel_verdict = _kernel_verdict_for_target(
                            pushed,
                            args.generate_layers,
                            use_generated_predecessor_evidence=args.use_generated_predecessor_evidence,
                            predecessor=predecessor,
                            cheap_prune_only=False,
                        )
                        timing["residual_full_kernel"] += time.perf_counter() - tick
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
                        cheap_prune_only=args.cheap_prune_only,
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
                    listed_pairs.add((pushed, predecessor))
                capture_reasons = set(args.capture_kernel_reason)
                if strict in set(args.capture_verdict) or effective_kernel_verdict[1] in capture_reasons:
                    if args.write_all_captures or len(selected_records) < args.max_capture:
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
            predecessor_features[_predecessor_feature(predecessor)] += 1
            target_features[_target_feature(pushed, pushed_swap)] += 1
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
    if args.predecessor_family_summary:
        print("predecessor_push_families:")
        for key, count in predecessor_push_families.most_common(args.top):
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
        if residual_target_features:
            print("residual_target_features:")
            for key, count in residual_target_features.most_common(args.top):
                print(f"  {key}: {count}")
        if residual_predecessor_features:
            print("residual_predecessor_features:")
            for key, count in residual_predecessor_features.most_common(args.top):
                print(f"  {key}: {count}")
        if args.predecessor_family_summary and residual_predecessor_push_families:
            print("residual_predecessor_push_families:")
            for key, count in residual_predecessor_push_families.most_common(args.top):
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
    if args.write_pairs:
        args.write_pairs.parent.mkdir(parents=True, exist_ok=True)
        args.write_pairs.write_text(
            "\n".join(f"{target}\t{predecessor}" for target, predecessor in sorted(listed_pairs)) + "\n",
            encoding="utf-8",
        )
        print(f"pairs_written={args.write_pairs}")
        print(f"pairs_written_count={len(listed_pairs)}")
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
            "listed_pairs": len(listed_pairs),
            "write_list_kernel_verdict": args.write_list_kernel_verdict,
            "write_list_kernel_reason": list(args.write_list_kernel_reason),
            "stop_reason": stop_reason,
            "raw_truncated": stop_reason != "exhausted",
            "rejected": dict(rejected),
            "target_verdicts": {repr(key): count for key, count in target_verdicts.items()},
            "target_kernel_verdicts": {repr(key): count for key, count in target_kernel_verdicts.items()},
            "residual_target_features": {repr(key): count for key, count in residual_target_features.items()},
            "residual_predecessor_features": {repr(key): count for key, count in residual_predecessor_features.items()},
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
    parser.add_argument("--exclude-stackable-predecessors", action="store_true")
    parser.add_argument("--skip-predecessor-details", action="store_true")
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--classify-targets", action="store_true")
    parser.add_argument("--kernel-only-classify", action="store_true")
    parser.add_argument("--dedupe-predecessors-before-push", action="store_true")
    parser.add_argument("--dedupe-targets-before-classify", action="store_true")
    parser.add_argument("--cheap-prune-only", action="store_true")
    parser.add_argument("--classify-residual-full", action="store_true")
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
    parser.add_argument("--write-all-captures", action="store_true")
    parser.add_argument("--write-targets", type=Path)
    parser.add_argument("--write-predecessors", type=Path)
    parser.add_argument("--write-pairs", type=Path)
    parser.add_argument("--write-list-kernel-verdict", choices=("all", "possible", "impossible", "unknown"), default="all")
    parser.add_argument("--write-list-kernel-reason", action="append", default=[])
    parser.add_argument("--write-summary-json", type=Path)
    parser.add_argument("--training-cache", type=Path, help="Read this cache when valid, otherwise write it after training.")
    parser.add_argument("--read-training-cache", type=Path)
    parser.add_argument("--write-training-cache", type=Path)
    parser.add_argument("--replay-captured", type=Path, action="append", default=[])
    parser.add_argument("--replay-captured-glob", action="append", default=[])
    parser.add_argument("--estimate-generation-space", action="store_true")
    parser.add_argument("--pp-essential-profile", action="store_true")
    parser.add_argument("--frontier-signature-profile", action="store_true")
    parser.add_argument("--frontier-data-profile", action="store_true")
    parser.add_argument("--predecessor-frontier-data-profile", action="store_true")
    parser.add_argument("--predecessor-family-data-profile", action="store_true")
    parser.add_argument("--predecessor-new-family-candidates", action="store_true")
    parser.add_argument("--predecessor-family-summary", action="store_true")
    parser.add_argument("--predecessor-family-mode", choices=("coarse", "exact"), default="coarse")
    parser.add_argument("--classify-new-family-candidates", action="store_true")
    parser.add_argument("--frontier-base-layers", type=int, default=0)
    parser.add_argument("--frontier-signature-mode", choices=("exact", "classes", "mask_counts", "counts"), default="exact")
    parser.add_argument("--high-layer-pp-smoke", default="", help="Comma-separated generated layer counts, e.g. 20,50,100.")
    parser.add_argument("--smoke-abstract-sequences", type=int, default=5)
    parser.add_argument("--smoke-raw-tests", type=int, default=12)
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
    if args.estimate_generation_space:
        return estimate_generation_space(args)
    if args.pp_essential_profile:
        return sample_pp_essential_profile(args)
    if args.frontier_signature_profile:
        return frontier_signature_profile(args)
    if args.frontier_data_profile:
        return frontier_data_profile(args)
    if args.predecessor_frontier_data_profile:
        return predecessor_frontier_data_profile(args)
    if args.predecessor_family_data_profile:
        return predecessor_family_data_profile(args)
    if args.predecessor_new_family_candidates:
        if args.seed_count <= 1:
            return predecessor_new_family_candidates(args)
        exit_code = 0
        base_seed = args.seed
        base_write_targets = args.write_targets
        base_write_pairs = args.write_pairs
        pretrained, training_time, sequence_time, training_cache_hit = _load_or_train(args)
        print("shared_training=True")
        print(f"shared_training_cache_hit={training_cache_hit}")
        print(f"shared_training_time={training_time:.6f}s")
        print(f"shared_sequence_time={sequence_time:.6f}s")
        for offset in range(args.seed_count):
            args.seed = base_seed + offset
            if base_write_targets is not None:
                args.write_targets = base_write_targets.with_name(
                    f"{base_write_targets.stem}_seed{args.seed}{base_write_targets.suffix}"
                )
            if base_write_pairs is not None:
                args.write_pairs = base_write_pairs.with_name(
                    f"{base_write_pairs.stem}_seed{args.seed}{base_write_pairs.suffix}"
                )
            print(f"=== seed={args.seed} ===")
            exit_code = max(exit_code, predecessor_new_family_candidates(args, pretrained=pretrained))
        return exit_code
    if args.high_layer_pp_smoke:
        return high_layer_pp_smoke(args)
    if args.seed_count <= 1:
        return generate(args)
    exit_code = 0
    base_seed = args.seed
    base_write_captured = args.write_captured
    base_write_targets = args.write_targets
    base_write_predecessors = args.write_predecessors
    base_write_pairs = args.write_pairs
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
        if base_write_pairs is not None:
            args.write_pairs = base_write_pairs.with_name(
                f"{base_write_pairs.stem}_seed{args.seed}{base_write_pairs.suffix}"
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
