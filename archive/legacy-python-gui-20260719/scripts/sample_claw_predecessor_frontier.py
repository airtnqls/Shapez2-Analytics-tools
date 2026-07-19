from __future__ import annotations

import argparse
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
from analyze_claw_preimages import _claw_predecessor


TARGET_TOP_FRONTIER = frozenset(
    {
        "-ScS",
        "S-Sc",
        "cS-S",
        "ScS-",
        "Sc--",
        "--cS",
        "S--c",
        "c--S",
        "--Sc",
        "cS--",
        "-cS-",
        "-Sc-",
        "c---",
        "--c-",
        "-c--",
        "---c",
    }
)


def _random_layer(rng: random.Random, alphabet: tuple[str, ...], weights: tuple[float, ...]) -> str:
    return "".join(rng.choices(alphabet, weights, k=4))


def _random_predecessor(rng: random.Random, layers: int, alphabet: tuple[str, ...], weights: tuple[float, ...]) -> str:
    top_q = rng.randrange(4)
    rows = [_random_layer(rng, alphabet, weights) for _ in range(layers - 1)]
    rows.append("".join("c" if q == top_q else "-" for q in range(4)))
    return sfa.normalize_code(":".join(rows))


def _frontier_bucket(predecessor: str, layers: int) -> tuple[str, str]:
    if not sfa.bitmask_physics_stable(predecessor):
        return "reject", "predecessor_unstable"
    target = sfa.bitmask_push_pin(predecessor, layers)
    if not target:
        return "reject", "empty_target"
    target_parts = target.split(":")
    target_top = target_parts[-1]
    if target_top not in TARGET_TOP_FRONTIER:
        return "reject", "target_top_not_claw_frontier"
    removal = sfa.bitmask_layer_removal_context(target)[:3]
    if not removal[1]:
        return "reject", "target_removes_no_crystal"
    if removal[0] <= 0:
        return "reject", "target_no_layer_removal"
    if sfa.claw_bottom_floor_reject_core_verdict(target) is not None:
        return "reject", "target_bottom_floor_reject"
    swap = sfa.bitmask_swap_impossibility(predecessor)
    if swap == "swap_both_blocked":
        return "reject", "predecessor_swap_both_blocked"
    return "accept", f"pred_swap={swap}|target_top={target_top}|rem={removal}"


def sample(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    alphabet = tuple(args.alphabet)
    raw_weights = tuple(float(part) for part in args.weights.split(","))
    if len(raw_weights) != len(alphabet):
        raise ValueError("--weights length must match --alphabet length")

    started = time.perf_counter()
    total = 0
    verdicts: Counter[str] = Counter()
    buckets: Counter[str] = Counter()
    examples: dict[str, str] = {}
    while total < args.samples:
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        predecessor = _random_predecessor(rng, args.layers, alphabet, raw_weights)
        total += 1
        verdict, bucket = _frontier_bucket(predecessor, args.layers)
        verdicts[verdict] += 1
        buckets[bucket] += 1
        if verdict == "accept" and bucket not in examples:
            examples[bucket] = f"{sfa.bitmask_push_pin(predecessor, args.layers)} <- {predecessor}"

    print(f"layers={args.layers}")
    print(f"samples={total}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("verdicts:")
    for key, count in verdicts.most_common():
        print(f"  {key}: {count}")
    print("buckets:")
    for key, count in buckets.most_common(args.top):
        print(f"  {key}: {count}")
        if key in examples and args.examples:
            print(f"    example={examples[key]}")
    return 0


def verify_known(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = accept = 0
    buckets: Counter[str] = Counter()
    samples: dict[str, str] = {}
    for code in sfa.iter_data_codes(args.known_data, max_layers=args.layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        target = sfa.normalize_code(code)
        if not target:
            continue
        total += 1
        predecessor = _claw_predecessor(target)
        verdict, bucket = _frontier_bucket(predecessor, args.layers)
        if verdict == "accept":
            accept += 1
        buckets[bucket] += 1
        if verdict != "accept" and bucket not in samples:
            samples[bucket] = f"{target} <- {predecessor}"
    print(f"known_data={args.known_data}")
    print(f"layers={args.layers}")
    print(f"known_total={total}")
    print(f"known_accept={accept}")
    print(f"known_accept_rate={100.0 * accept / total if total else 100:.6f}%")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("known_buckets:")
    for key, count in buckets.most_common(args.top):
        print(f"  {key}: {count}")
        if key in samples and args.examples:
            print(f"    example={samples[key]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample top unique-c predecessor frontier candidates.")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--samples", type=int, default=20000)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--alphabet", default="-SPc")
    parser.add_argument("--weights", default="0.25,0.35,0.20,0.20")
    parser.add_argument("--top", type=int, default=24)
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--known-data", type=Path)
    args = parser.parse_args()
    if args.known_data is not None:
        return verify_known(args)
    return sample(args)


if __name__ == "__main__":
    raise SystemExit(main())
