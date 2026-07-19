from __future__ import annotations

import argparse
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


def _rotate_layer_text(layer: str, turns: int) -> str:
    turns %= 4
    out = layer
    for _ in range(turns):
        out = out[3] + out[:3]
    return out


def _rotate_code_text(code: str, turns: int) -> str:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return ""
    return sfa.normalize_code(":".join(_rotate_layer_text(layer, turns) for layer in normalized.split(":")))


def _sorted_by_highest_c(code: str) -> str | None:
    normalized = sfa.normalize_code(code)
    if not normalized:
        return None
    parts = normalized.split(":")
    c_positions = [(layer, q) for layer, text in enumerate(parts) for q, ch in enumerate(text) if ch == "c"]
    if not c_positions:
        return None
    highest = max(layer for layer, _q in c_positions)
    highest_qs = [q for layer, q in c_positions if layer == highest]
    if len(highest_qs) != 1:
        return None
    return _rotate_code_text(normalized, -highest_qs[0])


def _rule_results(code: str) -> dict[str, bool]:
    normalized = sfa.normalize_code(code)
    parts = normalized.split(":") if normalized else []
    sorted_code = _sorted_by_highest_c(normalized)
    sorted_parts = sorted_code.split(":") if sorted_code else []
    c_positions = [(layer, q) for layer, text in enumerate(parts) for q, ch in enumerate(text) if ch == "c"]
    highest = max((layer for layer, _q in c_positions), default=-1)
    first = parts[0] if parts else "----"
    sorted_first = sorted_parts[0] if sorted_parts else "----"
    sorted_top = sorted_parts[-1] if sorted_parts else "----"
    return {
        "one_highest_c": sum(1 for layer, _q in c_positions if layer == highest) == 1,
        "sorted_top_q3_empty": bool(sorted_parts) and sorted_top[2] == "-",
        "first_floor_p_gt_1": sum(ch == "P" for ch in first) > 1,
        "sorted_first_floor_p_gt_1": sum(ch == "P" for ch in sorted_first) > 1,
        "first_floor_no_c": "c" not in first,
        "sorted_first_floor_no_c": "c" not in sorted_first,
        "first_floor_s_lt_2": sum(ch == "S" for ch in first) < 2,
        "sorted_first_floor_s_lt_2": sum(ch == "S" for ch in sorted_first) < 2,
        "sorted_not_all_q3_empty": any(layer[2] != "-" for layer in sorted_parts),
        "sorted_floor_1_to_3_q3_not_empty": all(layer[2] != "-" for layer in sorted_parts[: min(3, len(sorted_parts))]),
        "sorted_no_dash_dash_c_dash": all(layer != "--c-" for layer in sorted_parts),
    }


def audit(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    total = 0
    pass_counts: Counter[str] = Counter()
    fail_examples: defaultdict[str, list[str]] = defaultdict(list)
    layer_counts: Counter[int] = Counter()
    for code in sfa.iter_data_codes(args.data, max_layers=args.layers):
        if args.limit and total >= args.limit:
            break
        if args.max_seconds and time.perf_counter() - started > args.max_seconds:
            break
        normalized = sfa.normalize_code(code)
        if not normalized:
            continue
        total += 1
        layer_counts[len(normalized.split(":"))] += 1
        for name, passed in _rule_results(normalized).items():
            if passed:
                pass_counts[name] += 1
            elif len(fail_examples[name]) < args.max_examples:
                fail_examples[name].append(normalized)

    print(f"input={args.data}")
    print(f"layers={args.layers}")
    print(f"total={total}")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print("layer_counts:")
    for key, count in sorted(layer_counts.items()):
        print(f"  {key}: {count}")
    print("rule_pass_counts:")
    for name in sorted(pass_counts):
        count = pass_counts[name]
        print(f"  {name}: {count}/{total} ({100.0 * count / total if total else 100:.6f}%)")
    if fail_examples:
        print("fail_examples:")
        for name in sorted(fail_examples):
            print(f"  {name}:")
            for example in fail_examples[name]:
                print(f"    {example}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit user-observed claw note rules on claw datasets.")
    parser.add_argument("--data", type=Path, default=PROJECT_ROOT / "data" / "all40171clawsnohybrid.txt")
    parser.add_argument("--layers", type=int, default=5)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-seconds", type=float, default=120.0)
    parser.add_argument("--max-examples", type=int, default=3)
    return audit(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
