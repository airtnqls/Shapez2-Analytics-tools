from __future__ import annotations

import argparse
import contextlib
import io
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


def _legacy_type(code: str) -> tuple[str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        from shape import Shape
        from shape_classifier import analyze_shape

        result, reason = analyze_shape(code, Shape.from_string(code))
    return str(result), str(reason)


def _skip_type(code: str) -> tuple[str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        from shape import Shape

        return sfa.cached_skip_shape_analysis(repr(Shape.from_string(code)))


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from data_operations import simplify_shape
        from shape import Shape

        raw = claw_process(repr(Shape.from_string(code)))
        return sfa.normalize_code(simplify_shape(raw) if raw else "")


def _top_signature(code: str) -> str:
    normalized = sfa.normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts:
        return "empty"
    top = parts[-1]
    penult = parts[-2] if len(parts) >= 2 else "none"
    return f"{penult}>{top}|rem={sfa.bitmask_layer_removal_context(normalized)[:3]}"


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = processed = push_matches = empty_pred = errors = 0
    unique_predecessors: set[str] = set()
    predecessor_fanout: Counter[str] = Counter()
    pred_type_counts: Counter[tuple[str, str]] = Counter()
    pred_skip_type_counts: Counter[tuple[str, str]] = Counter()
    target_layers: Counter[int] = Counter()
    predecessor_layers: Counter[int] = Counter()
    target_top_signatures: Counter[str] = Counter()
    predecessor_top_signatures: Counter[str] = Counter()
    mismatch_samples: list[str] = []
    error_samples: list[str] = []
    fanout_samples: defaultdict[str, list[str]] = defaultdict(list)

    for code in sfa.iter_data_codes(args.data, max_layers=args.layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        target_layers[len(target.split(":"))] += 1
        try:
            pred = _claw_predecessor(target)
            processed += 1
        except Exception as exc:
            errors += 1
            if len(error_samples) < args.max_samples:
                error_samples.append(f"{target}\terror={type(exc).__name__}:{exc}")
            continue
        if not pred:
            empty_pred += 1
            if len(mismatch_samples) < args.max_samples:
                mismatch_samples.append(f"{target}\tempty_predecessor")
            continue
        unique_predecessors.add(pred)
        predecessor_layers[len(pred.split(":")) if pred else 0] += 1
        predecessor_fanout[pred] += 1
        if len(fanout_samples[pred]) < 3:
            fanout_samples[pred].append(target)
        target_top_signatures[_top_signature(target)] += 1
        predecessor_top_signatures[_top_signature(pred)] += 1
        replay = sfa.bitmask_push_pin(pred, max(args.layers, len(target.split(":"))))
        if replay == target:
            push_matches += 1
        elif len(mismatch_samples) < args.max_samples:
            mismatch_samples.append(f"{target}\tpred={pred}\tpush={replay}")
        if args.classify_predecessor:
            try:
                pred_type_counts[_legacy_type(pred)] += 1
            except Exception as exc:
                pred_type_counts[(type(exc).__name__, "classification_error")] += 1
            try:
                pred_skip_type_counts[_skip_type(pred)] += 1
            except Exception as exc:
                pred_skip_type_counts[(type(exc).__name__, "skip_classification_error")] += 1

    elapsed = time.perf_counter() - started
    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"processed={processed}")
    print(f"errors={errors}")
    print(f"empty_predecessor={empty_pred}")
    print(f"push_matches={push_matches}")
    print(f"push_match_rate={100.0 * push_matches / processed if processed else 100:.6f}%")
    print(f"unique_predecessors={len(unique_predecessors)}")
    print(f"elapsed={elapsed:.6f}s")
    if predecessor_fanout:
        print("top_predecessor_fanout:")
        for pred, count in predecessor_fanout.most_common(12):
            print(f"  {count}: {pred} -> {fanout_samples[pred]}")
    if pred_type_counts:
        print("predecessor_legacy_types:")
        for (kind, reason), count in pred_type_counts.most_common(20):
            print(f"  {count}: {kind}/{reason}")
    if pred_skip_type_counts:
        print("predecessor_skip_types:")
        for (kind, reason), count in pred_skip_type_counts.most_common(20):
            print(f"  {count}: {kind}/{reason}")
    print("target_layer_counts:")
    for layer, count in sorted(target_layers.items()):
        print(f"  {layer}: {count}")
    print("predecessor_layer_counts:")
    for layer, count in sorted(predecessor_layers.items()):
        print(f"  {layer}: {count}")
    print("target_top_signatures:")
    for sig, count in target_top_signatures.most_common(16):
        print(f"  {count}: {sig}")
    print("predecessor_top_signatures:")
    for sig, count in predecessor_top_signatures.most_common(16):
        print(f"  {count}: {sig}")
    if mismatch_samples:
        print("mismatch_samples:")
        for sample in mismatch_samples:
            print(sample)
    if error_samples:
        print("error_samples:")
        for sample in error_samples:
            print(sample)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze claw dataset as claw_process preimages.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--classify-predecessor", action="store_true")
    parser.add_argument("--max-samples", type=int, default=8)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
