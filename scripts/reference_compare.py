from __future__ import annotations

import argparse
import contextlib
import io
import random
import struct
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.symbolic_frontier_automaton import (  # noqa: E402
    bitmask_apply_physics,
    bitmask_push_pin,
    claw_failure_core_verdict,
    claw_verify_core_verdict,
    iter_data_codes_by_file,
    iter_random_codes,
    hybrid_rescue_core_verdict,
    layer_removal_core_verdict,
    normalize_code,
    physics_core_verdict,
    reference_cpcp_verdict,
    reference_cpcp_swappable_verdict,
    reference_stackability_core_verdict,
    pp_minimal_witness,
    pp_subtype_candidate,
    bitmask_stackable_bases,
    stackability_core_verdict,
    swap_core_verdict,
    symbolic_verdict,
    SymbolicFrontierAutomaton,
)
from scripts.half_set_automaton import (  # noqa: E402
    accepts as half_dfa_accepts,
    build_min_dfa,
    encode_half_word,
    load_reference_half_words,
    load_stable_reference_gap_words,
)


REF_DIR = PROJECT_ROOT / "reference_projects" / "shapez2-cpcp1998"


def build_harness(layers: int) -> Path:
    exe = REF_DIR / f"op_harness{layers}.exe"
    cmd = [
        "g++",
        "-o",
        str(exe),
        "op_harness.cpp",
        "-std=c++23",
        "-O3",
        f"-DCONFIG_LAYER={layers}",
    ]
    subprocess.run(cmd, cwd=REF_DIR, check=True, timeout=60)
    return exe


def run_ref(exe: Path, op: str, codes: list[str]) -> tuple[list[str], float, str]:
    payload = "\n".join(codes) + "\n"
    started = time.perf_counter()
    proc = subprocess.run(
        [str(exe), op],
        input=payload,
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    wall = time.perf_counter() - started
    outputs = [normalize_code(line) for line in proc.stdout.splitlines()]
    return outputs, wall, proc.stderr.strip()


def run_python(op: str, codes: list[str], layers: int) -> tuple[list[str], float]:
    started = time.perf_counter()
    if op == "collapse":
        outputs = [bitmask_apply_physics(code) for code in codes]
    elif op == "pin":
        outputs = [bitmask_push_pin(code, layers) for code in codes]
    else:
        raise ValueError(op)
    return outputs, time.perf_counter() - started


def _shape_bits(code: str, layers: int) -> int:
    code = normalize_code(code)
    parts = code.split(":") if code else []
    while len(parts) < layers:
        parts.append("----")
    bits = 0
    mapping = {"-": 0, "P": 1, "S": 2, "c": 3}
    for l, layer in enumerate(parts[:layers]):
        for q, ch in enumerate(layer):
            bits |= mapping.get(ch, 2) << (2 * (l * 4 + q))
    return bits


def _bits_to_code(bits: int, layers: int) -> str:
    chars = "-PSc"
    out = []
    for l in range(layers):
        out.append("".join(chars[(bits >> (2 * (l * 4 + q))) & 3] for q in range(4)))
    return normalize_code(":".join(out))


def _rotate_bits(bits: int, layers: int, angle: int) -> int:
    out = 0
    for l in range(layers):
        for q in range(4):
            value = (bits >> (2 * (l * 4 + q))) & 3
            nq = (q - angle) % 4
            out |= value << (2 * (l * 4 + nq))
    return out


def _flip_bits(bits: int, layers: int) -> int:
    out = 0
    for l in range(layers):
        for q in range(4):
            value = (bits >> (2 * (l * 4 + q))) & 3
            nq = 3 - q
            out |= value << (2 * (l * 4 + nq))
    return out


def _equiv_shape_min(bits: int, layers: int) -> int:
    variants = []
    for angle in range(4):
        rot = _rotate_bits(bits, layers, angle)
        variants.append(rot)
        variants.append(_flip_bits(rot, layers))
    return min(variants)


def _equiv_half_min(bits: int, layers: int) -> int:
    flipped = _rotate_bits(_flip_bits(bits, layers), layers, 2)
    return min(bits, flipped)


def _load_cpcp_dump(layers: int) -> tuple[set[int], set[int]]:
    dump = REF_DIR / f"dump{layers}.bin"
    data = dump.read_bytes()
    if layers <= 4:
        width = 4
        fmt = "<I"
    else:
        width = 8
        fmt = "<Q"
    pos = 0
    half_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    halves = set(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(half_count))
    pos += half_count * width
    shape_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    shapes = set(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(shape_count))
    return halves, shapes


def run_reference_lookup(args: argparse.Namespace, codes: list[str]) -> tuple[list[str], float]:
    started = time.perf_counter()
    halves, shapes = _load_cpcp_dump(args.layers)
    if args.half_dfa:
        half_words = load_reference_half_words(args.layers)
        dfa_start, dfa_transitions, dfa_accepting = build_min_dfa(half_words, args.layers)
    else:
        dfa_start = 0
        dfa_transitions = {}
        dfa_accepting = set()
    mask_half = 0
    for l in range(args.layers):
        for q in range(2):
            mask_half |= 3 << (2 * (l * 4 + q))
    outputs = []
    for code in codes:
        bits = _shape_bits(code, args.layers)
        creatable = False
        for angle in range(2):
            rotated = _rotate_bits(bits, args.layers, angle)
            left = _equiv_half_min(rotated & mask_half, args.layers)
            right = _equiv_half_min(_rotate_bits(bits, args.layers, angle + 2) & mask_half, args.layers)
            if args.half_dfa:
                left_ok = half_dfa_accepts(encode_half_word(left, args.layers), dfa_start, dfa_transitions, dfa_accepting)
                right_ok = half_dfa_accepts(encode_half_word(right, args.layers), dfa_start, dfa_transitions, dfa_accepting)
            else:
                left_ok = left in halves
                right_ok = right in halves
            if left_ok and right_ok:
                creatable = True
                break
        if not creatable:
            creatable = _equiv_shape_min(bits, args.layers) in shapes
        outputs.append("possible" if creatable else "impossible")
    return outputs, time.perf_counter() - started


def run_reference_reason(args: argparse.Namespace, codes: list[str]) -> tuple[list[str], float]:
    started = time.perf_counter()
    outputs = []
    for code in codes:
        verdict = reference_cpcp_verdict(code, args.layers)
        outputs.append(verdict[1] if verdict else "reference_missing_dump")
    return outputs, time.perf_counter() - started


def sample_reference_decomposition(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    _halves, shapes = _load_cpcp_dump(args.layers)
    shape_bits = list(shapes)
    if not args.no_shuffle:
        rng.shuffle(shape_bits)
    limit = min(args.limit, len(shape_bits))
    swappable = stackable = pp_like = 0
    samples: list[str] = []
    started = time.perf_counter()
    for bits in shape_bits[:limit]:
        code = _bits_to_code(bits, args.layers)
        if reference_cpcp_swappable_verdict(code, args.layers):
            swappable += 1
        elif reference_stackability_core_verdict(code, args.layers):
            stackable += 1
        else:
            pp_like += 1
            if len(samples) < args.show:
                samples.append(code)
    elapsed = time.perf_counter() - started
    print("mode=reference_decomposition_sample")
    print(f"layers={args.layers}")
    print(f"checked={limit}")
    print(f"swappable={swappable}")
    print(f"stackable={stackable}")
    print(f"pp_like={pp_like}")
    print(f"elapsed={elapsed:.6f}s")
    if samples:
        print("pp_like_samples:")
        for sample in samples:
            print(sample)
        print("pp_like_direct_predecessors:")
        direct_stats: Counter[str] = Counter()
        for sample in samples:
            layers = normalize_code(sample).split(":") if normalize_code(sample) else []
            predecessor = normalize_code(":".join(layers[1:]))
            pushed = bitmask_push_pin(predecessor, args.layers)
            ref = reference_cpcp_verdict(predecessor, args.layers)
            stack = reference_stackability_core_verdict(predecessor, args.layers)
            direct_stats[f"push{int(pushed == normalize_code(sample))}_ref{ref[0] if ref else 'none'}_stack{int(stack is not None)}"] += 1
            print(
                f"{sample}\tpre={predecessor}\tpush_match={int(pushed == normalize_code(sample))}"
                f"\tpre_ref={ref}\tpre_stack={stack}"
            )
        print("pp_like_direct_stats:")
        for key, count in direct_stats.most_common():
            print(f"  {count}\t{key}")
        print("pp_like_stackable_base_candidates:")
        for sample in samples:
            rows = []
            for base in bitmask_stackable_bases(sample):
                ref = reference_cpcp_verdict(base, args.layers)
                if ref is not None and ref[0] == "possible":
                    rows.append((base, ref))
            print(f"{sample}\tpossible_bases={len(rows)}")
            for base, ref in rows[: args.show]:
                print(f"  base={base}\tref={ref}")
        if args.pp_predecessor_probe:
            print("pp_like_predecessor_probe:")
            for sample in samples:
                hits = probe_pin_push_predecessors(sample, args.layers, args.pp_probe_limit)
                print(f"{sample}\thits={len(hits)}")
                for hit in hits[: args.show]:
                    print(f"  pre={hit[0]}\tref={hit[1]}\tstack={hit[2]}")
            print("pp_like_overflow_predecessor_probe:")
            for sample in samples:
                hits = probe_pin_push_overflow_predecessors(sample, args.layers, args.pp_probe_limit)
                print(f"{sample}\thits={len(hits)}")
                for hit in hits[: args.show]:
                    print(f"  pre={hit[0]}\tref={hit[1]}\tstack={hit[2]}")
            print("pp_like_masked_predecessor_probe:")
            for sample in samples:
                hits = probe_pin_push_masked_predecessors(sample, args.layers, args.pp_probe_limit)
                print(f"{sample}\thits={len(hits)}")
                for hit in hits[: args.show]:
                    print(f"  pre={hit[0]}\tref={hit[1]}\tstack={hit[2]}")
            print("pp_like_crystalize_predecessor_probe:")
            for sample in samples:
                hits = probe_crystalize_predecessors(sample, args.layers, args.pp_probe_limit)
                print(f"{sample}\thits={len(hits)}")
                for hit in hits[: args.show]:
                    print(f"  pre={hit[0]}\tref={hit[1]}\tstack={hit[2]}")
    return 0


def sample_recursive_stackability_closure(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    _halves, shapes = _load_cpcp_dump(args.layers)
    codes = [_bits_to_code(bits, args.layers) for bits in shapes]
    if not args.no_shuffle:
        rng.shuffle(codes)
    codes = codes[: min(args.limit, len(codes))]

    residual = set(codes)
    explained_by_round: list[int] = []
    seed_base_hits = 0
    classified_level: dict[str, int] = {}
    known_non_swappable_bases: set[str] = set()
    remaining = set(residual)
    base_cache = {code: bitmask_stackable_bases(code) for code in remaining}
    swappable_cache: dict[str, bool] = {}
    started = time.perf_counter()

    for round_index in range(1, args.recursive_rounds + 1):
        newly_explained: set[str] = set()
        for code in list(remaining):
            for base in base_cache[code]:
                if base not in swappable_cache:
                    swappable_cache[base] = reference_cpcp_swappable_verdict(base, args.layers) is not None
                if swappable_cache[base]:
                    newly_explained.add(code)
                    if round_index == 1:
                        seed_base_hits += 1
                    break
                if base in known_non_swappable_bases:
                    newly_explained.add(code)
                    break
        explained_by_round.append(len(newly_explained))
        if not newly_explained:
            break
        for code in newly_explained:
            classified_level[code] = round_index
        known_non_swappable_bases.update(newly_explained)
        remaining.difference_update(newly_explained)

    elapsed = time.perf_counter() - started
    print("mode=recursive_stackability_closure_sample")
    print(f"layers={args.layers}")
    print(f"checked={len(codes)}")
    print(f"initial_non_swappable={len(residual)}")
    print(f"round_1_seed_base_hits={seed_base_hits}")
    print(f"rounds_requested={args.recursive_rounds}")
    print(f"rounds_executed={len(explained_by_round)}")
    print(f"closure_explained={sum(explained_by_round)}")
    print(f"closure_remaining={len(remaining)}")
    print(f"elapsed={elapsed:.6f}s")
    for index, count in enumerate(explained_by_round, start=1):
        print(f"round_{index}_explained={count}")
    remaining_base_status = Counter()
    for code in remaining:
        has_ref_swappable = False
        has_ref_non_swappable = False
        has_ref_impossible = False
        for base in base_cache[code]:
            ref = reference_cpcp_verdict(base, args.layers)
            if ref is None:
                continue
            if ref[0] == "impossible":
                has_ref_impossible = True
            elif ref[1] == "reference_cpcp_swappable":
                has_ref_swappable = True
            elif ref[1] == "reference_cpcp_non_swappable":
                has_ref_non_swappable = True
        remaining_base_status[
            f"swappable{int(has_ref_swappable)}_nonswap{int(has_ref_non_swappable)}_impossible{int(has_ref_impossible)}"
        ] += 1
    if remaining_base_status:
        print("remaining_base_status:")
        for key, count in remaining_base_status.most_common():
            print(f"  {count}\t{key}")
    remaining_direct_stats = Counter()
    residual_base_in_remaining = 0
    residual_base_possible_external = 0
    external_base_stackability = Counter()
    pp_minimal_candidates = 0
    pp_minimal_samples: list[str] = []
    pp_minimal_direct_stats = Counter()
    pp_minimal_base_count = Counter()
    pp_minimal_push_miss_samples: list[str] = []
    pp_minimal_push_miss_features = Counter()
    pp_minimal_push_miss_delta_classes = Counter()
    pp_minimal_push_miss_bottom_pin_hits = 0
    pp_nonminimal_push_miss_bottom_pin_hits = 0
    pp_nonminimal_push_miss_total = 0
    pp_minimal_subtypes = Counter()
    derivative_base_parent_stats = Counter()
    derivative_base_subtypes = Counter()
    derivative_unclassified_base_features = Counter()
    derivative_unclassified_base_samples: list[str] = []
    derivative_unclassified_base_total = 0
    derivative_unclassified_base_zero_base_hits = 0
    derivative_unclassified_top_s_hits = 0
    pp_feature_pos = Counter()
    pp_feature_neg = Counter()
    for code in remaining:
        layers = normalize_code(code).split(":") if normalize_code(code) else []
        predecessor = normalize_code(":".join(layers[1:]))
        pushed = bitmask_push_pin(predecessor, args.layers)
        ref = reference_cpcp_verdict(predecessor, args.layers)
        stack = reference_stackability_core_verdict(predecessor, args.layers)
        remaining_direct_stats[
            f"push{int(pushed == normalize_code(code))}_ref{ref[0] if ref else 'none'}_stack{int(stack is not None)}"
        ] += 1
        has_remaining_base = False
        has_external_possible_base = False
        has_any_possible_base = False
        for base in base_cache[code]:
            if base in remaining:
                has_remaining_base = True
            ref_base = reference_cpcp_verdict(base, args.layers)
            if ref_base is not None and ref_base[0] == "possible" and base not in remaining:
                has_external_possible_base = True
                ext_stack = reference_stackability_core_verdict(base, args.layers)
                external_base_stackability[
                    "stackable" if ext_stack is not None else "not_stackable"
                ] += 1
            if ref_base is not None and ref_base[0] == "possible":
                has_any_possible_base = True
        residual_base_in_remaining += int(has_remaining_base)
        residual_base_possible_external += int(has_external_possible_base)
        feature_keys = _pp_feature_keys(code, len(base_cache[code]), pushed == normalize_code(code), ref, stack)
        if not has_any_possible_base:
            pp_minimal_candidates += 1
            if len(pp_minimal_samples) < args.show:
                pp_minimal_samples.append(code)
                _ = pp_minimal_witness(code, args.layers)
            pp_minimal_direct_stats[
                f"push{int(pushed == normalize_code(code))}_ref{ref[0] if ref else 'none'}_stack{int(stack is not None)}"
            ] += 1
            pp_minimal_base_count[str(len(base_cache[code]))] += 1
            pp_feature_pos.update(feature_keys)
            subtype = pp_subtype_candidate(code, args.layers)
            pp_minimal_subtypes[subtype.subtype] += 1
            if subtype.subtype == "bottom_pin_derivative_pp_candidate" and subtype.bottom_pin_base:
                base_witness = pp_minimal_witness(subtype.bottom_pin_base, args.layers)
                derivative_base_parent_stats[
                    f"push{int(base_witness.push_matches_target)}_ref{base_witness.predecessor_reference[0] if base_witness.predecessor_reference else 'none'}"
                    f"_stack{int(base_witness.predecessor_stackability is not None)}"
                ] += 1
                derivative_base_subtypes[pp_subtype_candidate(subtype.bottom_pin_base, args.layers).subtype] += 1
                recursive = pp_subtype_candidate(subtype.bottom_pin_base, args.layers)
                if recursive.subtype == "unclassified_pp_candidate":
                    derivative_unclassified_base_total += 1
                    if recursive.minimal.target_stackable_base_count == 0:
                        derivative_unclassified_base_zero_base_hits += 1
                    if any(_shape_delta_class(candidate, subtype.bottom_pin_base) == "top_layer_s_add_one" for candidate in bitmask_stackable_bases(subtype.bottom_pin_base)):
                        derivative_unclassified_top_s_hits += 1
                    if len(derivative_unclassified_base_samples) < args.show:
                        derivative_unclassified_base_samples.append(subtype.bottom_pin_base)
                    base_minimal = pp_minimal_witness(subtype.bottom_pin_base, args.layers)
                    derivative_unclassified_base_features.update(
                        _pp_feature_keys(
                            subtype.bottom_pin_base,
                            base_minimal.target_stackable_base_count,
                            base_minimal.push_matches_target,
                            base_minimal.predecessor_reference,
                            base_minimal.predecessor_stackability,
                        )
                    )
            if pushed != normalize_code(code):
                if len(pp_minimal_push_miss_samples) < args.show:
                    pp_minimal_push_miss_samples.append(code)
                pp_minimal_push_miss_features.update(feature_keys)
                unique_bases = bitmask_stackable_bases(code)
                if len(unique_bases) == 1:
                    pp_minimal_push_miss_delta_classes[_shape_delta_class(unique_bases[0], code)] += 1
                else:
                    pp_minimal_push_miss_delta_classes["non_unique_base"] += 1
                if any(_shape_delta_class(base, code) == "bottom_pin_add_one" for base in unique_bases):
                    pp_minimal_push_miss_bottom_pin_hits += 1
        else:
            pp_feature_neg.update(feature_keys)
            if pushed != normalize_code(code):
                pp_nonminimal_push_miss_total += 1
                if any(_shape_delta_class(base, code) == "bottom_pin_add_one" for base in base_cache[code]):
                    pp_nonminimal_push_miss_bottom_pin_hits += 1
    if remaining_direct_stats:
        print("remaining_direct_predecessor_status:")
        for key, count in remaining_direct_stats.most_common():
            print(f"  {count}\t{key}")
        print(f"remaining_with_residual_base_in_sample={residual_base_in_remaining}")
        print(f"remaining_with_external_possible_base={residual_base_possible_external}")
        print(f"pp_minimal_candidates={pp_minimal_candidates}")
        if pp_minimal_direct_stats:
            print("pp_minimal_direct_predecessor_status:")
            for key, count in pp_minimal_direct_stats.most_common():
                print(f"  {count}\t{key}")
        if pp_minimal_base_count:
            print("pp_minimal_candidate_base_count:")
            for key, count in pp_minimal_base_count.most_common():
                print(f"  {count}\tbases={key}")
        if external_base_stackability:
            print("external_possible_base_stackability:")
            for key, count in external_base_stackability.most_common():
                print(f"  {count}\t{key}")
        if pp_minimal_samples:
            print("pp_minimal_samples:")
            for sample in pp_minimal_samples:
                witness = pp_minimal_witness(sample, args.layers)
                print(
                    f"  {sample}\tpre={witness.predecessor}"
                    f"\tpush_match={int(witness.push_matches_target)}"
                    f"\tpre_ref={witness.predecessor_reference}"
                    f"\tpre_stack={witness.predecessor_stackability}"
                    f"\tbases={witness.target_stackable_base_count}"
                )
        if pp_minimal_push_miss_samples:
            print("pp_minimal_push_miss_samples:")
            for sample in pp_minimal_push_miss_samples:
                witness = pp_minimal_witness(sample, args.layers)
                unique_bases = bitmask_stackable_bases(sample)
                base = unique_bases[0] if len(unique_bases) == 1 else ""
                delta = _shape_delta_summary(base, sample) if base else "non_unique_base"
                print(
                    f"  {sample}\tpre={witness.predecessor}"
                    f"\tpush_match={int(witness.push_matches_target)}"
                    f"\tpre_ref={witness.predecessor_reference}"
                    f"\tpre_stack={witness.predecessor_stackability}"
                    f"\tbases={witness.target_stackable_base_count}"
                    f"\tbase={base or '-'}"
                    f"\tdelta={delta}"
                )
                if not base:
                    print("    candidate_delta_classes:")
                    for candidate in unique_bases[: args.show]:
                        print(
                            f"      base={candidate}"
                            f"\tclass={_shape_delta_class(candidate, sample)}"
                            f"\tdelta={_shape_delta_summary(candidate, sample)}"
                        )
        if pp_minimal_push_miss_features:
            print("pp_minimal_push_miss_feature_counts:")
            for key, count in pp_minimal_push_miss_features.most_common(args.show):
                print(f"  {count}\t{key}")
        if pp_minimal_push_miss_delta_classes:
            print("pp_minimal_push_miss_delta_classes:")
            for key, count in pp_minimal_push_miss_delta_classes.most_common():
                print(f"  {count}\t{key}")
        if pp_minimal_subtypes:
            print("pp_minimal_subtypes:")
            for key, count in pp_minimal_subtypes.most_common():
                print(f"  {count}\t{key}")
        if derivative_base_parent_stats:
            print("bottom_pin_derivative_base_parent_status:")
            for key, count in derivative_base_parent_stats.most_common():
                print(f"  {count}\t{key}")
        if derivative_base_subtypes:
            print("bottom_pin_derivative_base_subtypes:")
            for key, count in derivative_base_subtypes.most_common():
                print(f"  {count}\t{key}")
        if derivative_unclassified_base_samples:
            print("bottom_pin_derivative_unclassified_base_samples:")
            for sample in derivative_unclassified_base_samples:
                print(f"  {sample}\t{subtype_witness_line(sample, args.layers)}")
                recursive = pp_subtype_candidate(sample, args.layers)
                if recursive.subtype == "unclassified_pp_candidate" and recursive.minimal.target_stackable_base_count > 0:
                    print("    recursive_candidate_delta_classes:")
                    for candidate in bitmask_stackable_bases(sample)[: args.show]:
                        print(
                            f"      base={candidate}"
                            f"\tclass={_shape_delta_class(candidate, sample)}"
                            f"\tdelta={_shape_delta_summary(candidate, sample)}"
                        )
        if derivative_unclassified_base_features:
            print("bottom_pin_derivative_unclassified_base_feature_counts:")
            for key, count in derivative_unclassified_base_features.most_common(args.show):
                print(f"  {count}\t{key}")
        print(f"pp_minimal_push_miss_bottom_pin_hits={pp_minimal_push_miss_bottom_pin_hits}")
        print(f"pp_nonminimal_push_miss_total={pp_nonminimal_push_miss_total}")
        print(f"pp_nonminimal_push_miss_bottom_pin_hits={pp_nonminimal_push_miss_bottom_pin_hits}")
        print(f"derivative_unclassified_base_total={derivative_unclassified_base_total}")
        print(f"derivative_unclassified_base_zero_base_hits={derivative_unclassified_base_zero_base_hits}")
        print(f"derivative_unclassified_top_s_hits={derivative_unclassified_top_s_hits}")
        if pp_feature_pos:
            print("pp_feature_lift:")
            ranked = []
            pos_total = max(pp_minimal_candidates, 1)
            neg_total = max(len(remaining) - pp_minimal_candidates, 1)
            for key, pos_count in pp_feature_pos.items():
                neg_count = pp_feature_neg.get(key, 0)
                pos_rate = pos_count / pos_total
                neg_rate = neg_count / neg_total
                lift = pos_rate / max(neg_rate, 1e-9)
                ranked.append((lift, pos_count, neg_count, key))
            for lift, pos_count, neg_count, key in sorted(ranked, reverse=True)[: args.show]:
                print(f"  lift={lift:.3f}\tpos={pos_count}\tneg={neg_count}\t{key}")
    if args.show:
        level_counts = Counter(classified_level.values())
        print("classified_levels:")
        for level, count in sorted(level_counts.items()):
            label = f"stack_round_{level}"
            print(f"  {count}\t{label}")
        if remaining:
            print("remaining_samples:")
            for sample in list(remaining)[: args.show]:
                refs = []
                for base in bitmask_stackable_bases(sample):
                    if len(refs) >= args.show:
                        break
                    ref = reference_cpcp_verdict(base, args.layers)
                    refs.append((base, ref))
                print(f"{sample}\tcandidate_bases={len(refs)}")
                for base, ref in refs:
                    print(f"  base={base}\tref={ref}")
    return 0


def _target_pin_mask(code: str) -> int:
    normalized = normalize_code(code)
    if not normalized:
        return 0
    first = normalized.split(":")[0]
    return sum(1 << q for q, ch in enumerate(first) if ch == "P")


def _pp_feature_keys(
    code: str,
    base_count: int,
    direct_push_match: bool,
    predecessor_ref: tuple[str, str] | None,
    predecessor_stack: tuple[str, str] | None,
) -> list[str]:
    normalized = normalize_code(code)
    layers = normalized.split(":") if normalized else []
    bottom = layers[0] if layers else "----"
    top = layers[-1] if layers else "----"
    heights = []
    for q in range(4):
        h = 0
        for l, layer in enumerate(layers):
            if layer[q] != "-":
                h = l + 1
        heights.append(h)
    c_total = sum(layer.count("c") for layer in layers)
    p_total = sum(layer.count("P") for layer in layers)
    s_total = sum(layer.count("S") for layer in layers)
    keys = [
        f"depth={len(layers)}",
        f"base_count={base_count}",
        f"push_match={int(direct_push_match)}",
        f"pred_ref={predecessor_ref[0] if predecessor_ref else 'none'}",
        f"pred_stack={int(predecessor_stack is not None)}",
        f"bottom_p={bottom.count('P')}",
        f"bottom_c={bottom.count('c')}",
        f"bottom_s={bottom.count('S')}",
        f"top_p={top.count('P')}",
        f"top_c={top.count('c')}",
        f"top_s={top.count('S')}",
        f"total_p={p_total}",
        f"total_c={c_total}",
        f"total_s={s_total}",
        f"max_height={max(heights) if heights else 0}",
        f"min_nonzero_height={min((h for h in heights if h), default=0)}",
        f"occupied_columns={sum(1 for h in heights if h)}",
        f"height_profile={','.join(map(str, heights))}",
    ]
    return keys


def _shape_delta_summary(base: str, target: str) -> str:
    base_layers = normalize_code(base).split(":") if normalize_code(base) else []
    target_layers = normalize_code(target).split(":") if normalize_code(target) else []
    depth = max(len(base_layers), len(target_layers))
    rows = []
    for l in range(depth):
        b = base_layers[l] if l < len(base_layers) else "----"
        t = target_layers[l] if l < len(target_layers) else "----"
        changes = []
        for q, (bc, tc) in enumerate(zip(b, t)):
            if bc != tc:
                changes.append(f"{q}:{bc}>{tc}")
        if changes:
            rows.append(f"L{l}[{','.join(changes)}]")
    return ";".join(rows) if rows else "same"


def _shape_delta_class(base: str, target: str) -> str:
    base_layers = normalize_code(base).split(":") if normalize_code(base) else []
    target_layers = normalize_code(target).split(":") if normalize_code(target) else []
    depth = max(len(base_layers), len(target_layers))
    changes = []
    for l in range(depth):
        b = base_layers[l] if l < len(base_layers) else "----"
        t = target_layers[l] if l < len(target_layers) else "----"
        for q, (bc, tc) in enumerate(zip(b, t)):
            if bc != tc:
                changes.append((l, q, bc, tc))
    if len(changes) == 1:
        l, _q, bc, tc = changes[0]
        if l == 0 and bc == "-" and tc == "P":
            return "bottom_pin_add_one"
        if bc == "-" and tc == "S" and l == depth - 1:
            return "top_layer_s_add_one"
        return f"single_change_L{l}_{bc}>{tc}"
    return f"multi_change_{len(changes)}"


def subtype_witness_line(code: str, layers: int) -> str:
    subtype = pp_subtype_candidate(code, layers)
    minimal = subtype.minimal
    return (
        f"subtype={subtype.subtype}"
        f"\tpre={minimal.predecessor}"
        f"\tpush_match={int(minimal.push_matches_target)}"
        f"\tpre_ref={minimal.predecessor_reference}"
        f"\tpre_stack={minimal.predecessor_stackability}"
        f"\tbases={minimal.target_stackable_base_count}"
        f"\tbottom_pin_base={subtype.bottom_pin_base or '-'}"
    )


def probe_pin_push_predecessors(code: str, layers: int, limit: int) -> list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]]:
    target = normalize_code(code)
    target_layers = target.split(":") if target else []
    pin_mask = _target_pin_mask(target)
    allowed = []
    for q in range(4):
        if pin_mask & (1 << q):
            allowed.append("PSc")
        else:
            allowed.append("-")
    candidates: list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]] = []
    tried = 0
    base_tail = target_layers[1:]

    def rec(q: int, chars: list[str]) -> None:
        nonlocal tried
        if tried >= limit:
            return
        if q == 4:
            tried += 1
            first = "".join(chars)
            pre = normalize_code(":".join([first] + base_tail))
            if bitmask_push_pin(pre, layers) != target:
                return
            ref = reference_cpcp_verdict(pre, layers)
            stack = reference_stackability_core_verdict(pre, layers)
            if ref is not None and ref[0] == "possible" or stack is not None:
                candidates.append((pre, ref, stack))
            return
        for ch in allowed[q]:
            chars.append(ch)
            rec(q + 1, chars)
            chars.pop()

    rec(0, [])
    return candidates


def probe_pin_push_overflow_predecessors(code: str, layers: int, limit: int) -> list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]]:
    target = normalize_code(code)
    target_layers = target.split(":") if target else []
    if len(target_layers) < 2:
        return []
    base = target_layers[1:]
    alphabet = "-PSc"
    candidates: list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]] = []
    tried = 0

    def rec(chars: list[str]) -> None:
        nonlocal tried
        if tried >= limit:
            return
        if len(chars) == 4:
            tried += 1
            top = "".join(chars)
            pre = normalize_code(":".join(base + [top]))
            if bitmask_push_pin(pre, layers) != target:
                return
            ref = reference_cpcp_verdict(pre, layers)
            stack = reference_stackability_core_verdict(pre, layers)
            if (ref is not None and ref[0] == "possible") or stack is not None:
                candidates.append((pre, ref, stack))
            return
        for ch in alphabet:
            chars.append(ch)
            rec(chars)
            chars.pop()

    rec([])
    return candidates


def probe_pin_push_masked_predecessors(code: str, layers: int, limit: int) -> list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]]:
    target = normalize_code(code)
    target_layers = target.split(":") if target else []
    if len(target_layers) < 2:
        return []
    pin_mask = _target_pin_mask(target)
    p1 = target_layers[2] if len(target_layers) > 2 else "----"
    p2 = target_layers[3] if len(target_layers) > 3 else "----"
    first_allowed = ["PSc" if pin_mask & (1 << q) else "-" for q in range(4)]
    alphabet = "-PSc"
    candidates: list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]] = []
    tried = 0

    def test(first: str, top: str) -> None:
        nonlocal tried
        if tried >= limit:
            return
        tried += 1
        pre = normalize_code(":".join([first, p1, p2, top]))
        if bitmask_push_pin(pre, layers) != target:
            return
        ref = reference_cpcp_verdict(pre, layers)
        stack = reference_stackability_core_verdict(pre, layers)
        if (ref is not None and ref[0] == "possible") or stack is not None:
            candidates.append((pre, ref, stack))

    def rec_first(q: int, chars: list[str]) -> None:
        if q == 4:
            first = "".join(chars)
            rec_top(first, [])
            return
        for ch in first_allowed[q]:
            chars.append(ch)
            rec_first(q + 1, chars)
            chars.pop()

    def rec_top(first: str, chars: list[str]) -> None:
        if tried >= limit:
            return
        if len(chars) == 4:
            test(first, "".join(chars))
            return
        for ch in alphabet:
            chars.append(ch)
            rec_top(first, chars)
            chars.pop()

    rec_first(0, [])
    return candidates


def bitmask_crystalize(code: str) -> str:
    normalized = normalize_code(code)
    if not normalized:
        return ""
    parts = normalized.split(":")
    out = []
    for layer in parts:
        out.append("".join("c" if ch in "-P" else ch for ch in layer))
    return normalize_code(":".join(out))


def probe_crystalize_predecessors(code: str, layers: int, limit: int) -> list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]]:
    target = normalize_code(code)
    target_layers = target.split(":") if target else []
    c_positions = [(l, q) for l, layer in enumerate(target_layers) for q, ch in enumerate(layer) if ch == "c"]
    candidates: list[tuple[str, tuple[str, str] | None, tuple[str, str] | None]] = []
    tried = 0
    mutable = [list(layer) for layer in target_layers]

    def rec(index: int) -> None:
        nonlocal tried
        if tried >= limit:
            return
        if index == len(c_positions):
            tried += 1
            pre = normalize_code(":".join("".join(layer) for layer in mutable))
            if bitmask_crystalize(pre) != target:
                return
            ref = reference_cpcp_verdict(pre, layers)
            stack = reference_stackability_core_verdict(pre, layers)
            if (ref is not None and ref[0] == "possible") or stack is not None:
                candidates.append((pre, ref, stack))
            return
        l, q = c_positions[index]
        original = mutable[l][q]
        for ch in "-Pc":
            mutable[l][q] = ch
            rec(index + 1)
        mutable[l][q] = original

    rec(0)
    return candidates


def reference_half_diagnostics(args: argparse.Namespace, mismatches: list[tuple[str, str, str, str]]) -> None:
    if not mismatches:
        return
    halves, _shapes = _load_cpcp_dump(args.layers)
    stable_gap_words = load_stable_reference_gap_words(args.layers)
    mask_half = 0
    for l in range(args.layers):
        for q in range(2):
            mask_half |= 3 << (2 * (l * 4 + q))
    pair_status: Counter[str] = Counter()
    gap_status: Counter[str] = Counter()
    missing: Counter[str] = Counter()
    for code, _symbolic, _reference, _bucket in mismatches:
        bits = _shape_bits(code, args.layers)
        for angle in range(2):
            rotated = _rotate_bits(bits, args.layers, angle)
            left = _equiv_half_min(rotated & mask_half, args.layers)
            right = _equiv_half_min(_rotate_bits(bits, args.layers, angle + 2) & mask_half, args.layers)
            left_ok = left in halves
            right_ok = right in halves
            pair_status[f"angle{angle}:L{int(left_ok)}R{int(right_ok)}"] += 1
            if not left_ok:
                missing[_bits_to_code(left, args.layers)] += 1
                if encode_half_word(left, args.layers) in stable_gap_words:
                    gap_status["left_stable_gap"] += 1
            if not right_ok:
                missing[_bits_to_code(right, args.layers)] += 1
                if encode_half_word(right, args.layers) in stable_gap_words:
                    gap_status["right_stable_gap"] += 1
    print("half_pair_status:")
    for key, count in pair_status.most_common(args.show):
        print(f"  {count}\t{key}")
    print("top_missing_halves:")
    for half, count in missing.most_common(args.show):
        print(f"  {count}\t{half}")
    if gap_status:
        print("stable_gap_missing:")
        for key, count in gap_status.most_common():
            print(f"  {count}\t{key}")


def _symbolic_kernel_verdict(automaton: SymbolicFrontierAutomaton, code: str, layers: int, use_stackability: bool) -> tuple[str, str]:
    verdict, bucket = symbolic_verdict(automaton, code, layers)
    if verdict != "unknown":
        return verdict, bucket
    for fn in (physics_core_verdict, swap_core_verdict, layer_removal_core_verdict):
        kernel = fn(code)
        if kernel is not None:
            return kernel
    if use_stackability:
        kernel = stackability_core_verdict(code)
        if kernel is not None:
            return kernel
    for fn in (claw_verify_core_verdict, hybrid_rescue_core_verdict, claw_failure_core_verdict):
        kernel = fn(code)
        if kernel is not None:
            return kernel
    return "unknown", "unknown"


def run_symbolic_lookup(args: argparse.Namespace, codes: list[str]) -> tuple[list[str], list[str], float]:
    automaton = SymbolicFrontierAutomaton(corner_mode="strict", max_depth=args.layers)
    started = time.perf_counter()
    outputs = []
    buckets = []
    for code in codes:
        if args.reference_decomposition:
            ref_swap = reference_cpcp_swappable_verdict(code, args.layers)
            if ref_swap is not None:
                outputs.append(ref_swap[0])
                buckets.append(ref_swap[1])
                continue
            ref_stack = reference_stackability_core_verdict(code, args.layers)
            if ref_stack is not None:
                outputs.append(ref_stack[0])
                buckets.append(ref_stack[1])
                continue
            outputs.append("unknown")
            buckets.append("reference_decomposition_unknown")
            continue
        if args.reference_cpcp:
            ref_kernel = reference_cpcp_verdict(code, args.layers)
            if ref_kernel is not None:
                outputs.append(ref_kernel[0])
                buckets.append(ref_kernel[1])
                continue
        if args.reference_stackability:
            ref_stack = reference_stackability_core_verdict(code, args.layers)
            if ref_stack is not None:
                outputs.append(ref_stack[0])
                buckets.append(ref_stack[1])
                continue
        if args.fallback:
            verdict, bucket = _symbolic_kernel_verdict(automaton, code, args.layers, args.stackability_core)
            outputs.append(verdict)
            buckets.append(bucket)
        else:
            verdict, bucket = symbolic_verdict(automaton, code, args.layers)
            outputs.append(verdict)
            buckets.append(bucket)
    return outputs, buckets, time.perf_counter() - started


def load_codes(args: argparse.Namespace) -> list[str]:
    if args.random:
        codes = [normalize_code(c) for c in iter_random_codes(args.random, args.layers, args.seed)]
    else:
        codes = list(iter_data_codes_by_file(
            args.data,
            args.per_file,
            args.seed,
            shuffle=not args.no_shuffle,
            max_layers=args.layers,
        ))
    if args.stable_only:
        codes = [code for code in codes if bitmask_apply_physics(code) == normalize_code(code)]
    return codes[: args.limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--op", choices=("collapse", "pin"), default="collapse")
    parser.add_argument("--lookup", action="store_true")
    parser.add_argument("--sample-reference-decomposition", action="store_true")
    parser.add_argument("--sample-recursive-stackability-closure", action="store_true")
    parser.add_argument("--reference-reasons", action="store_true")
    parser.add_argument("--pp-predecessor-probe", action="store_true")
    parser.add_argument("--pp-probe-limit", type=int, default=512)
    parser.add_argument("--recursive-rounds", type=int, default=4)
    parser.add_argument("--fallback", action="store_true")
    parser.add_argument("--stackability-core", action="store_true")
    parser.add_argument("--reference-cpcp", action="store_true")
    parser.add_argument("--reference-stackability", action="store_true")
    parser.add_argument("--reference-decomposition", action="store_true")
    parser.add_argument("--random", type=int, default=0)
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--per-file", type=int, default=80)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--stable-only", action="store_true")
    parser.add_argument("--half-diagnostics", action="store_true")
    parser.add_argument("--half-dfa", action="store_true")
    parser.add_argument("--show", type=int, default=10)
    args = parser.parse_args()

    codes = load_codes(args)
    if not codes:
        if args.sample_reference_decomposition:
            return sample_reference_decomposition(args)
        if args.sample_recursive_stackability_closure:
            return sample_recursive_stackability_closure(args)
        print("no_codes=1")
        return 1

    if args.sample_reference_decomposition:
        return sample_reference_decomposition(args)
    if args.sample_recursive_stackability_closure:
        return sample_recursive_stackability_closure(args)

    if args.lookup:
        ref_out, ref_time = run_reference_lookup(args, codes)
        if args.reference_reasons:
            ref_reasons, _reason_time = run_reference_reason(args, codes)
        else:
            ref_reasons = [""] * len(codes)
        sym_out, sym_buckets, sym_time = run_symbolic_lookup(args, codes)
        mismatches = [
            (code, s, r, b)
            for code, s, r, b in zip(codes, sym_out, ref_out, sym_buckets)
            if s != "unknown" and s != r
        ]
        mismatch_buckets: dict[str, int] = {}
        for _code, _s, _r, bucket in mismatches:
            mismatch_buckets[bucket] = mismatch_buckets.get(bucket, 0) + 1
        unknowns = sum(1 for v in sym_out if v == "unknown")
        ref_reason_counts = Counter(ref_reasons)
        print("mode=lookup")
        print(f"layers={args.layers}")
        print(f"count={len(codes)}")
        print(f"symbolic_time={sym_time:.6f}s")
        print(f"reference_time={ref_time:.6f}s")
        print(f"symbolic_unknown={unknowns}")
        print(f"known_mismatches={len(mismatches)}")
        if args.reference_reasons:
            print("reference_reasons:")
            for reason, count in ref_reason_counts.most_common(args.show):
                print(f"  {count}\t{reason}")
        for bucket, count in sorted(mismatch_buckets.items(), key=lambda item: -item[1])[: args.show]:
            print(f"mismatch_bucket\t{count}\t{bucket}")
        for code, s, r, b in mismatches[: args.show]:
            print(f"mismatch\t{code}\tsymbolic={s}\treference={r}\tbucket={b}")
        if args.half_diagnostics:
            reference_half_diagnostics(args, mismatches)
        return 1 if mismatches else 0

    exe = build_harness(args.layers)
    py_out, py_time = run_python(args.op, codes, args.layers)
    ref_out, ref_time, ref_log = run_ref(exe, args.op, codes)
    mismatches = [
        (code, p, r)
        for code, p, r in zip(codes, py_out, ref_out)
        if normalize_code(p) != normalize_code(r)
    ]
    print(f"op={args.op}")
    print(f"layers={args.layers}")
    print(f"count={len(codes)}")
    print(f"python_time={py_time:.6f}s")
    print(f"reference_wall_time={ref_time:.6f}s")
    print(f"reference_log={ref_log}")
    print(f"speed_ref_over_python={(py_time / ref_time) if ref_time else 0:.3f}x")
    print(f"mismatches={len(mismatches)}")
    for code, p, r in mismatches[: args.show]:
        print(f"mismatch\t{code}\tpython={p}\treference={r}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
