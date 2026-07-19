from __future__ import annotations

import argparse
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
from analyze_claw_preimages import _claw_predecessor


def _grid(code: str, layers: int) -> list[list[str]]:
    normalized = sfa.normalize_code(code)
    rows = [list(layer) for layer in normalized.split(":")] if normalized else []
    while len(rows) < layers:
        rows.append(list("----"))
    return rows[:layers]


def _coords(code: str, layers: int) -> dict[tuple[int, int], str]:
    rows = _grid(code, layers)
    return {
        (l, q): ch
        for l, row in enumerate(rows)
        for q, ch in enumerate(row)
        if ch != "-"
    }


def _top_nonempty_layer(code: str) -> int:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return -1
    parts = normalized.split(":")
    for idx in range(len(parts) - 1, -1, -1):
        if parts[idx].strip("-"):
            return idx
    return -1


def _shape_signature(target: str, predecessor: str, layers: int) -> str:
    target_coords = _coords(target, layers)
    pred_coords = _coords(predecessor, layers)
    replay = sfa.bitmask_push_pin(predecessor, layers)
    replay_coords = _coords(replay, layers)
    inserted_pin = sum(1 for q in range(4) if _grid(predecessor, layers)[0][q] != "-")
    added = Counter()
    removed = Counter()
    changed = Counter()
    replay_delta = Counter()
    for coord in set(target_coords) | set(pred_coords):
        t = target_coords.get(coord, "-")
        p = pred_coords.get(coord, "-")
        if p == "-" and t != "-":
            added[t] += 1
        elif p != "-" and t == "-":
            removed[p] += 1
        elif p != t:
            changed[f"{p}->{t}"] += 1
    for coord in set(target_coords) | set(replay_coords):
        t = target_coords.get(coord, "-")
        r = replay_coords.get(coord, "-")
        if r != t:
            replay_delta[f"{r}->{t}"] += 1
    return (
        f"pred_top={_top_nonempty_layer(predecessor)} "
        f"target_top={_top_nonempty_layer(target)} "
        f"pin_cols={inserted_pin} "
        f"add={tuple(sorted(added.items()))} "
        f"rem={tuple(sorted(removed.items()))} "
        f"chg={tuple(sorted(changed.items()))} "
        f"replay_delta={sum(replay_delta.values())}"
    )


def _frontier_signature(target: str, predecessor: str, layers: int) -> str:
    pred_rows = _grid(predecessor, layers)
    target_rows = _grid(target, layers)
    pred_bottom = "".join(pred_rows[0])
    target_bottom = "".join(target_rows[0])
    target_top = "".join(target_rows[_top_nonempty_layer(target)])
    pred_top = "".join(pred_rows[_top_nonempty_layer(predecessor)])
    target_removal = sfa.bitmask_layer_removal_context(target)[:3]
    pred_swap = sfa.bitmask_swap_impossibility(predecessor)
    return (
        f"pred_bottom={pred_bottom} target_bottom={target_bottom} "
        f"pred_top={pred_top} target_top={target_top} "
        f"target_rem={target_removal} pred_swap={pred_swap}"
    )


def analyze(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = ok = 0
    shape_sigs: Counter[str] = Counter()
    frontier_sigs: Counter[str] = Counter()
    pred_swap_counts: Counter[str] = Counter()
    samples: dict[str, str] = {}
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
        replay = sfa.bitmask_push_pin(predecessor, args.layers)
        if replay == target:
            ok += 1
        sig = _shape_signature(target, predecessor, args.layers)
        fsig = _frontier_signature(target, predecessor, args.layers)
        shape_sigs[sig] += 1
        frontier_sigs[fsig] += 1
        pred_swap_counts[str(sfa.bitmask_swap_impossibility(predecessor))] += 1
        samples.setdefault(sig, f"{target}\t<- {predecessor}")

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"pinpush_replay_ok={ok}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("predecessor_swap_counts:")
    for key, count in pred_swap_counts.most_common():
        print(f"  {key}: {count}")
    print("shape_delta_signatures:")
    for sig, count in shape_sigs.most_common(args.top):
        print(f"  {count}: {sig}")
        if args.samples:
            print(f"    sample={samples[sig]}")
    print("frontier_signatures:")
    for sig, count in frontier_sigs.most_common(args.top):
        print(f"  {count}: {sig}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze pin-push frontier deltas for claw preimages.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--samples", action="store_true")
    return analyze(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
