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

import symbolic_frontier_automaton as sfa

with contextlib.redirect_stdout(io.StringIO()):
    from claw_tracer import claw_process as _claw_process
    from data_operations import simplify_shape as _simplify_shape
    from shape import Shape as _Shape
    from shape_classifier import analyze_shape as _analyze_shape


def _legacy_type(code: str) -> tuple[str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        result, reason = _analyze_shape(code, _Shape.from_string(code))
    return str(result), str(reason)


def _skip_type(code: str) -> tuple[str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        return sfa.cached_skip_shape_analysis(repr(_Shape.from_string(code)))


def _claw_predecessor(code: str) -> str:
    with contextlib.redirect_stdout(io.StringIO()):
        raw = _claw_process(repr(_Shape.from_string(code)))
        return sfa.normalize_code(_simplify_shape(raw) if raw else "")


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
    pred_decomposition_counts: Counter[str] = Counter()
    pred_axis_counts: Counter[str] = Counter()
    target_layers: Counter[int] = Counter()
    predecessor_layers: Counter[int] = Counter()
    predecessor_c_counts: Counter[int] = Counter()
    predecessor_highest_c: Counter[tuple[int, int, str]] = Counter()
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
        pred_parts = pred.split(":") if pred else []
        predecessor_layers[len(pred_parts)] += 1
        predecessor_c_counts[sum(layer.count("c") for layer in pred_parts)] += 1
        highest_c_layer = -1
        highest_c_count = 0
        highest_c_text = ""
        for layer_idx in range(len(pred_parts) - 1, -1, -1):
            count = pred_parts[layer_idx].count("c")
            if count:
                highest_c_layer = layer_idx
                highest_c_count = count
                highest_c_text = pred_parts[layer_idx]
                break
        predecessor_highest_c[(highest_c_layer, highest_c_count, highest_c_text)] += 1
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
        if args.decompose_predecessor:
            if sfa.reference_cpcp_swappable_witness(pred, args.layers) is not None:
                pred_decomposition_counts["reference_swappable"] += 1
            elif sfa.reference_stackability_core_verdict(pred, args.layers) is not None:
                pred_decomposition_counts["reference_stackable"] += 1
            else:
                subtype = sfa.pp_subtype_candidate(pred, args.layers).subtype
                pred_decomposition_counts[subtype] += 1
        if args.axis_decompose_predecessor:
            swap_reason = sfa.bitmask_swap_impossibility(pred)
            if swap_reason is None:
                pred_axis_counts["half_swappable"] += 1
            elif sfa.bitmask_stackability_witnesses(pred):
                pred_axis_counts[f"stackable_after_{swap_reason}"] += 1
            else:
                subtype = sfa.pp_subtype_candidate(pred, args.layers).subtype
                pred_axis_counts[f"pp:{subtype}"] += 1

    elapsed = time.perf_counter() - started
    summary = {
        "input": str(args.data),
        "layers": args.layers,
        "total": total,
        "processed": processed,
        "errors": errors,
        "empty_predecessor": empty_pred,
        "push_matches": push_matches,
        "push_match_rate": (100.0 * push_matches / processed if processed else 100.0),
        "unique_predecessors": len(unique_predecessors),
        "elapsed": elapsed,
        "predecessor_axis_decomposition": dict(pred_axis_counts),
        "predecessor_decomposition": dict(pred_decomposition_counts),
        "target_layer_counts": dict(target_layers),
        "predecessor_layer_counts": dict(predecessor_layers),
        "predecessor_c_counts": dict(predecessor_c_counts),
        "predecessor_highest_c": {
            f"layer={layer}|c_count={c_count}|text={text}": count
            for (layer, c_count, text), count in predecessor_highest_c.items()
        },
        "target_top_signatures": dict(target_top_signatures),
        "predecessor_top_signatures": dict(predecessor_top_signatures),
    }
    if args.write_json:
        args.write_json.parent.mkdir(parents=True, exist_ok=True)
        args.write_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
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
    if pred_decomposition_counts:
        print("predecessor_decomposition:")
        for key, count in pred_decomposition_counts.most_common(24):
            print(f"  {key}: {count}")
    if pred_axis_counts:
        print("predecessor_axis_decomposition:")
        for key, count in pred_axis_counts.most_common(24):
            print(f"  {key}: {count}")
    print("target_layer_counts:")
    for layer, count in sorted(target_layers.items()):
        print(f"  {layer}: {count}")
    print("predecessor_layer_counts:")
    for layer, count in sorted(predecessor_layers.items()):
        print(f"  {layer}: {count}")
    print("predecessor_c_counts:")
    for c_count, count in predecessor_c_counts.most_common(20):
        print(f"  {c_count}: {count}")
    print("predecessor_highest_c:")
    for (layer, c_count, text), count in predecessor_highest_c.most_common(20):
        print(f"  {count}: layer={layer} c_count={c_count} text={text}")
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
    if args.write_json:
        print(f"wrote_json={args.write_json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze claw dataset as claw_process preimages.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--classify-predecessor", action="store_true")
    parser.add_argument("--decompose-predecessor", action="store_true")
    parser.add_argument("--axis-decompose-predecessor", action="store_true")
    parser.add_argument("--write-json", type=Path, default=None)
    parser.add_argument("--max-samples", type=int, default=8)
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
