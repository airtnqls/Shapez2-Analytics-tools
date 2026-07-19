from __future__ import annotations

import argparse
import contextlib
import io
import json
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

import generate_six_layer_abstract_claw_candidates as gen
import symbolic_frontier_automaton as sfa

with contextlib.redirect_stdout(io.StringIO()):
    from claw_tracer import claw_process as _claw_process
    from data_operations import simplify_shape as _simplify_shape
    from shape import Shape as _Shape


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        raw = _claw_process(repr(_Shape.from_string(code)))
        return sfa.normalize_code(_simplify_shape(raw) if raw else "")


def _ngram_index(raw_index: int, layers: int, order: int, train_layers: int) -> int:
    top_relative = gen._ngram_index(raw_index, layers, order, "top_relative")
    min_train_top_relative = -(train_layers - order)
    return -1 if top_relative < min_train_top_relative else top_relative


def _pair_in_guaranteed_raw_choices(
    pair: tuple[str, str],
    abstract: tuple[str, str],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
    max_raw_per_layer: int,
) -> bool:
    raw = sorted(raw_by_abstract.get(abstract, ()), key=lambda item: (-raw_pair_counts[item], item))
    if not raw:
        return False
    if max_raw_per_layer and len(raw) > max_raw_per_layer:
        raw = raw[:max_raw_per_layer]
    return pair in raw


def _pair_rank(
    pair: tuple[str, str],
    abstract: tuple[str, str],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
) -> int:
    raw = sorted(raw_by_abstract.get(abstract, ()), key=lambda item: (-raw_pair_counts[item], item))
    try:
        return raw.index(pair) + 1
    except ValueError:
        return 0


def _sequence_coverage(
    sequence: tuple[tuple[str, str], ...],
    args: argparse.Namespace,
    abstract_ngrams: set[tuple[int, tuple[tuple[str, str], ...]]],
    raw_by_abstract: dict[tuple[str, str], set[tuple[str, str]]],
    raw_pair_counts: Counter[tuple[str, str]],
) -> tuple[bool, bool, str]:
    abstract_sequence = tuple(gen._abstract_pair(pair, args.abstract_mode) for pair in sequence)
    if len(abstract_sequence) < args.order:
        return False, False, "short_sequence"

    for index in range(len(abstract_sequence) - args.order + 1):
        gram = abstract_sequence[index : index + args.order]
        key = (_ngram_index(index, len(abstract_sequence), args.order, args.train_layers), gram)
        if key not in abstract_ngrams and (-1, gram) not in abstract_ngrams:
            return False, False, "missing_abstract_ngram"

    guaranteed = True
    for pair, abstract in zip(sequence, abstract_sequence):
        if pair not in raw_by_abstract.get(abstract, ()):
            return False, False, "missing_raw_pair"
        if not _pair_in_guaranteed_raw_choices(
            pair,
            abstract,
            raw_by_abstract,
            raw_pair_counts,
            args.max_raw_per_layer,
        ):
            guaranteed = False
    return True, guaranteed, "covered"


def measure(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    args.selected_train_subtypes = gen._selected_subtypes(args.train_subtypes)
    train_args = argparse.Namespace(**vars(args))
    records, abstract_ngrams, raw_by_abstract, raw_pair_counts = gen._train(train_args)

    total = valid_predecessor = selected_subtype = grammar_recalled = guaranteed_recalled = 0
    replay_mismatch = 0
    subtype_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    failure_by_subtype: defaultdict[str, Counter[str]] = defaultdict(Counter)
    required_raw_rank_counts: Counter[int] = Counter()
    required_raw_rank_by_subtype: defaultdict[str, Counter[int]] = defaultdict(Counter)
    samples: list[dict[str, str]] = []

    for code in sfa.iter_data_codes(args.data, max_layers=args.layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            failure_counts["stopped_by_max_seconds"] += 1
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        predecessor = _claw_predecessor(target)
        if not predecessor:
            failure_counts["missing_predecessor"] += 1
            continue
        if sfa.bitmask_push_pin(predecessor, args.layers) != target:
            replay_mismatch += 1
            failure_counts["push_mismatch"] += 1
            continue
        valid_predecessor += 1
        subtype = sfa.pp_subtype_candidate(predecessor, args.layers).subtype
        subtype_counts[subtype] += 1
        if subtype not in args.selected_train_subtypes:
            failure_counts["subtype_not_selected"] += 1
            failure_by_subtype[subtype]["subtype_not_selected"] += 1
            continue
        selected_subtype += 1

        angle_results = []
        for angle in range(2):
            sequence = gen._pair_sequence(predecessor, args.layers, angle)
            available, guaranteed, reason = _sequence_coverage(
                sequence,
                args,
                abstract_ngrams,
                raw_by_abstract,
                raw_pair_counts,
            )
            abstract_sequence = tuple(gen._abstract_pair(pair, args.abstract_mode) for pair in sequence)
            ranks = [
                _pair_rank(pair, abstract, raw_by_abstract, raw_pair_counts)
                for pair, abstract in zip(sequence, abstract_sequence)
            ]
            max_rank = max(ranks) if ranks and all(rank > 0 for rank in ranks) else 0
            reconstructed = gen._predecessor_from_sequence(sequence)
            angle_results.append((available, guaranteed, reason, reconstructed == predecessor, max_rank))

        available_angles = [
            max_rank
            for available, _guaranteed, _reason, reconstructed, max_rank in angle_results
            if available and reconstructed and max_rank > 0
        ]
        if available_angles:
            grammar_recalled += 1
            required_rank = min(available_angles)
            required_raw_rank_counts[required_rank] += 1
            required_raw_rank_by_subtype[subtype][required_rank] += 1
        else:
            reason = next(
                (reason for available, _guaranteed, reason, _reconstructed, _max_rank in angle_results if not available),
                "not_reconstructed",
            )
            failure_counts[reason] += 1
            failure_by_subtype[subtype][reason] += 1
            if len(samples) < args.max_samples:
                samples.append({"target": target, "predecessor": predecessor, "subtype": subtype, "reason": reason})
            continue

        if any(guaranteed and reconstructed for _available, guaranteed, _reason, reconstructed, _max_rank in angle_results):
            guaranteed_recalled += 1
        else:
            failure_counts["not_in_guaranteed_raw_head"] += 1
            failure_by_subtype[subtype]["not_in_guaranteed_raw_head"] += 1
            if len(samples) < args.max_samples:
                samples.append(
                    {
                        "target": target,
                        "predecessor": predecessor,
                        "subtype": subtype,
                        "reason": "not_in_guaranteed_raw_head",
                    }
                )

    elapsed = time.perf_counter() - started
    grammar_pct = (grammar_recalled / selected_subtype * 100.0) if selected_subtype else 0.0
    guaranteed_pct = (guaranteed_recalled / selected_subtype * 100.0) if selected_subtype else 0.0
    result = {
        "input": str(args.data),
        "layers": args.layers,
        "train_layers": args.train_layers,
        "order": args.order,
        "abstract_mode": args.abstract_mode,
        "train_subtypes": list(args.selected_train_subtypes),
        "max_raw_per_layer": args.max_raw_per_layer,
        "training_records": records,
        "abstract_ngrams": len(abstract_ngrams),
        "abstract_classes": len(raw_by_abstract),
        "total": total,
        "valid_predecessor": valid_predecessor,
        "selected_subtype": selected_subtype,
        "push_mismatch": replay_mismatch,
        "grammar_recalled": grammar_recalled,
        "grammar_recall_pct": grammar_pct,
        "guaranteed_recalled": guaranteed_recalled,
        "guaranteed_recall_pct": guaranteed_pct,
        "elapsed": elapsed,
        "subtype_counts": dict(subtype_counts),
        "failure_counts": dict(failure_counts),
        "failure_by_subtype": {key: dict(value) for key, value in failure_by_subtype.items()},
        "required_raw_rank_counts": dict(required_raw_rank_counts),
        "required_raw_rank_by_subtype": {
            key: dict(value) for key, value in required_raw_rank_by_subtype.items()
        },
        "samples": samples,
    }

    print(f"input={result['input']}")
    print(f"layers={args.layers}")
    print(f"train_subtypes={','.join(args.selected_train_subtypes)}")
    print(f"order={args.order}")
    print(f"abstract_mode={args.abstract_mode}")
    print(f"max_raw_per_layer={args.max_raw_per_layer}")
    print(f"training_records={records}")
    print(f"total={total}")
    print(f"valid_predecessor={valid_predecessor}")
    print(f"selected_subtype={selected_subtype}")
    print(f"grammar_recalled={grammar_recalled} ({grammar_pct:.6f}%)")
    print(f"guaranteed_recalled={guaranteed_recalled} ({guaranteed_pct:.6f}%)")
    print(f"elapsed={elapsed:.6f}s")
    print("subtype_counts:")
    for key, count in subtype_counts.most_common(args.top):
        print(f"  {key}: {count}")
    print("failure_counts:")
    for key, count in failure_counts.most_common(args.top):
        print(f"  {key}: {count}")
    print("failure_by_subtype:")
    for subtype, counter in sorted(failure_by_subtype.items()):
        print(f"  {subtype}:")
        for key, count in counter.most_common(args.top):
            print(f"    {key}: {count}")
    print("required_raw_rank_counts:")
    for key, count in sorted(required_raw_rank_counts.items())[: args.top]:
        print(f"  {key}: {count}")
    if required_raw_rank_counts:
        cumulative = 0
        print("required_raw_rank_cumulative:")
        total_ranked = sum(required_raw_rank_counts.values())
        for key, count in sorted(required_raw_rank_counts.items()):
            cumulative += count
            if key <= args.top or key in {16, 24, 32, 48, 64, 96, 128} or cumulative == total_ranked:
                print(f"  <= {key}: {cumulative} ({cumulative / total_ranked * 100.0:.6f}%)")
    if samples:
        print("samples:")
        for sample in samples:
            print(json.dumps(sample, ensure_ascii=False, sort_keys=True))

    if args.write_summary_json:
        args.write_summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_summary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"summary_written={args.write_summary_json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure whether claw predecessor generation grammar covers known claw preimages.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--train-layers", type=int, default=5)
    parser.add_argument("--train-subtypes", default="all_pp")
    parser.add_argument("--order", type=int, default=3)
    parser.add_argument("--abstract-mode", choices=("classes", "mask_counts", "counts", "raw"), default="classes")
    parser.add_argument("--max-raw-per-layer", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-train-seconds", type=float, default=0.0)
    parser.add_argument("--top", type=int, default=16)
    parser.add_argument("--max-samples", type=int, default=8)
    parser.add_argument("--write-summary-json", type=Path)
    return measure(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
