from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import symbolic_frontier_automaton as sfa


def _shape_text(shape: object) -> str:
    return repr(shape)


def _wrap_counter(module: object, name: str, stats: Counter[str], changed: bool = False) -> None:
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        stats[f"{name}.calls"] += 1
        before = _shape_text(args[0]) if changed and args else ""
        result = original(*args, **kwargs)
        if changed and args and _shape_text(args[0]) != before:
            stats[f"{name}.changed"] += 1
        return result

    setattr(module, name, wrapper)


def _wrap_return(module: object, name: str, stats: Counter[str], labeler: Callable[[object], str]) -> None:
    original = getattr(module, name)

    def wrapper(*args, **kwargs):
        stats[f"{name}.calls"] += 1
        result = original(*args, **kwargs)
        stats[f"{name}.return.{labeler(result)}"] += 1
        return result

    setattr(module, name, wrapper)


def _install_hooks(stats: Counter[str]) -> None:
    import claw_tracer

    for name in (
        "_relocate_s_pieces",
        "_fill_c_from_pins",
        "_fill_opposite_quadrant",
        "_move_pieces_based_on_empty_spot_around_p",
    ):
        _wrap_counter(claw_tracer, name, stats, changed=True)

    for name in (
        "_find_s_star_group",
        "_find_twice_floating_s_group",
    ):
        _wrap_return(claw_tracer, name, stats, lambda result: f"size_{len(result)}")

    _wrap_return(claw_tracer, "_move_s_group", stats, lambda result: f"shift_{result}")

    def relocation_label(result: object) -> str:
        target, fill_c, moved_s = result
        return f"target_{target}_fill_{len(fill_c)}_moved_{len(moved_s)}"

    _wrap_return(claw_tracer, "_find_s_relocation_spot", stats, relocation_label)

    def c4_label(result: object) -> str:
        return str(result)

    for name in ("_check_c_placement_4th_layer", "_check_c_placement_3rd_layer"):
        if hasattr(claw_tracer, name):
            _wrap_return(claw_tracer, name, stats, c4_label)

    original_s_valid = claw_tracer._check_s_placement_validity

    def s_valid_wrapper(shape, l, q, hypothetical_group_positions, highest_c_layer, c_quad_idx):
        stats["_check_s_placement_validity.calls"] += 1
        stats[f"_check_s_placement_validity.layer_{l}"] += 1
        result = original_s_valid(shape, l, q, hypothetical_group_positions, highest_c_layer, c_quad_idx)
        stats[f"_check_s_placement_validity.result_{result}"] += 1
        return result

    claw_tracer._check_s_placement_validity = s_valid_wrapper


def audit(args: argparse.Namespace) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import claw_process
        from shape import Shape

    stats: Counter[str] = Counter()
    _install_hooks(stats)

    started = time.perf_counter()
    total = ok = errors = 0
    top_c_layers: Counter[int] = Counter()
    top_c_quads: Counter[int] = Counter()
    target_layers: Counter[int] = Counter()
    samples: list[str] = []

    with contextlib.redirect_stdout(io.StringIO()):
        from claw_tracer import _get_static_info
        from data_operations import simplify_shape
        from shape import Shape

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
            shape = Shape.from_string(target)
            _pins, highest_c_layer, c_quad_idx = _get_static_info(shape)
            top_c_layers[highest_c_layer] += 1
            top_c_quads[c_quad_idx] += 1
            pred = sfa.normalize_code(simplify_shape(claw_process(repr(shape))))
            if sfa.bitmask_push_pin(pred, max(args.layers, len(target.split(":")))) == target:
                ok += 1
            elif len(samples) < args.max_samples:
                samples.append(f"{target}\tpred={pred}\treplay_mismatch")
        except Exception as exc:
            errors += 1
            if len(samples) < args.max_samples:
                samples.append(f"{target}\terror={type(exc).__name__}:{exc}")

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"ok_replay={ok}")
    print(f"errors={errors}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("target_layer_counts:")
    for key, count in sorted(target_layers.items()):
        print(f"  {key}: {count}")
    print("highest_c_layers:")
    for key, count in sorted(top_c_layers.items()):
        print(f"  {key}: {count}")
    print("highest_c_quads:")
    for key, count in sorted(top_c_quads.items()):
        print(f"  {key}: {count}")
    print("rule_stats:")
    for key, count in stats.most_common(80):
        print(f"  {key}: {count}")
    if samples:
        print("samples:")
        for sample in samples:
            print(sample)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit which claw_process rules fire on claw datasets.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-samples", type=int, default=8)
    return audit(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
