from __future__ import annotations

import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import ALPHABET, is_craftable_column
from backend.corner_half.corner_regions import Route, analyze_column
from backend.corner_half.structural_physics import code, column, is_stable, push_pin


def _rightmost_cluster_left(s: str, char: str) -> int:
    for i in range(len(s) - 1, -1, -1):
        if s[i] == char:
            start = i
            while start > 0 and s[start - 1] == char:
                start -= 1
            return start - 1 if start > 0 else 0
    return -1


def _nearest_left(a: list[str], start: int, target: str) -> int:
    for i in range(start - 1, -1, -1):
        if a[i] == target:
            return i
    return -1


def _left_run(a: list[str], pos: int, target: str) -> int:
    count = 0
    for i in range(pos - 1, -1, -1):
        if a[i] != target:
            break
        count += 1
    return count


def legacy_predecessor_rows(s: str, cap: int) -> list[list[str]]:
    """Typed transcription of legacy ``build_pinable_shape``.

    The legacy routine returns rows in the project's A,B,D,C serialization.
    Here we return explicit ring-order A,B,C,D rows, where structural q2 is the
    all-crystal overflow column and q3 is the relay/drop column.
    """
    if not s or len(s) != cap:
        raise ValueError("audit uses full-height normalized columns")
    l2 = _rightmost_cluster_left(s, "c")

    work = list(s)
    c_indices = [i for i, ch in enumerate(work) if ch == "c"]
    drop_sources: list[int] = []
    drop_heights: list[int] = []
    drop_targets: list[int] = []
    for c_idx in c_indices:
        if c_idx <= 0 or work[c_idx - 1] != "-":
            continue
        source = _nearest_left(work, c_idx, "S")
        if source < 0:
            continue
        gap = _left_run(work, source, "-")
        if gap == source:
            gap -= 1
        drop_sources.append(source)
        drop_heights.append(gap)
        drop_targets.append(c_idx - 1)
        work[source] = "-"

    base = work.copy()
    a = work.copy()
    highest_c = max((i for i, ch in enumerate(s) if ch == "c"), default=-1)
    if highest_c >= 0:
        for i in range(highest_c + 1):
            if a[i] == "-":
                a[i] = "c"
    for pos in drop_targets:
        a[pos] = "S"
    a = a[1:] + ["-"]
    if s[0] in "-S":
        for i, ch in enumerate(a):
            if ch == "c":
                a[i] = "-"
            else:
                break

    b = list(s)
    if l2 >= 0:
        for i in range(min(l2 + 1, len(b))):
            if b[i] == "-":
                b[i] = "P"
    b = ["S" if ch == "c" else ch for ch in b]
    if highest_c >= 0:
        for i in range(highest_c, len(b)):
            if b[i] == "-":
                b[i] = "S"
    b = b[1:] + ["-"]

    relay = ["-"] * cap
    original_positions = [i for i, ch in enumerate(s) if ch in "cS"]
    if l2 >= 0:
        for i in range(min(l2 + 1, cap)):
            relay[i] = "c"
    for pos in original_positions:
        if pos not in drop_sources and relay[pos] == "c":
            relay[pos] = "S"
    for pos, height in zip(drop_targets, drop_heights):
        relay[pos] = "S"
        for delta in range(1, height + 1):
            if pos - delta >= 0:
                relay[pos - delta] = "S"
    relay = relay[1:] + ["-"]

    overflow = ["c"] * cap
    if s[0] == "S":
        for i in range(len(a)):
            if a[i] == "-":
                if i + 1 >= len(a) or a[i + 1] != "-":
                    a[i] = "S"
                    if relay[i] == "S":
                        relay[i] = "c"
                        relay[0] = "S"
                    break
            else:
                break

    # legacy format_final_result(A,B,C,D) serializes A,B,D,C.
    return [[a[i], b[i], overflow[i], relay[i]] for i in range(cap)]


def relation(target: str, pushed_a: str) -> str:
    if pushed_a == target:
        return "exact"
    expected_receipt = ("P" if target and target[0] != "-" else "-") + target[1:]
    if pushed_a == expected_receipt.rstrip("-"):
        return "bottom-receipt"
    if len(pushed_a) == len(target) and pushed_a[1:] == target[1:]:
        return "bottom-only-difference"
    return "other"


def one(target: str) -> dict[str, object]:
    cap = len(target)
    rows = legacy_predecessor_rows(target, cap)
    pred_code = code(rows)
    stable = is_stable(rows)
    pushed = push_pin(rows, cap)
    out_a = column(pushed, 0)
    helpers = tuple(column(rows, q) for q in range(1, 4))
    helper_craftable = tuple(is_craftable_column(x) for x in helpers)
    witness = analyze_column(target)
    return {
        "target": target,
        "zoneKind": witness.zone.kind.value if witness.zone else None,
        "segments": list(witness.regions.segments),
        "predecessor": pred_code,
        "predecessorStable": stable,
        "helpers": helpers,
        "helperCraftable": helper_craftable,
        "pushedA": out_a,
        "relation": relation(target, out_a),
        "pushed": code(pushed),
    }


def exhaustive(max_len: int = 8) -> dict[str, object]:
    counts = Counter()
    by_zone: dict[str, Counter] = defaultdict(Counter)
    failures: dict[str, list[dict[str, object]]] = defaultdict(list)
    total_event = 0
    for length in range(1, max_len + 1):
        for chars in itertools.product(ALPHABET, repeat=length):
            if chars[-1] == "-":
                continue
            target = "".join(chars)
            if "c" not in target or not is_craftable_column(target):
                continue
            witness = analyze_column(target)
            if witness.route is not Route.EVENT:
                continue
            total_event += 1
            try:
                result = one(target)
            except Exception as exc:  # keep minimal counterexamples in the report
                counts["compiler-exception"] += 1
                if len(failures["compiler-exception"]) < 20:
                    failures["compiler-exception"].append({"target": target, "error": repr(exc)})
                continue
            zone = str(result["zoneKind"])
            rel = str(result["relation"])
            counts[f"relation:{rel}"] += 1
            by_zone[zone][f"relation:{rel}"] += 1
            if result["predecessorStable"]:
                counts["stable"] += 1
                by_zone[zone]["stable"] += 1
            else:
                counts["unstable"] += 1
                if len(failures["unstable"]) < 20:
                    failures["unstable"].append(result)
            if all(result["helperCraftable"]):
                counts["helpers-all-craftable"] += 1
            else:
                counts["helper-rejection"] += 1
                if len(failures["helper-rejection"]) < 20:
                    failures["helper-rejection"].append(result)
            if rel == "other" and len(failures["relation-other"]) < 30:
                failures["relation-other"].append(result)
    return {
        "maxLength": max_len,
        "eventColumns": total_event,
        "counts": dict(counts),
        "byZone": {key: dict(value) for key, value in sorted(by_zone.items())},
        "minimalFailures": failures,
    }


def family_audit(max_repeats: int = 100) -> dict[str, object]:
    rows = []
    for repeats in list(range(1, 17)) + [24, 32, 48, 64, 80, max_repeats]:
        target = "S" + "S-S-c" * repeats
        result = one(target)
        rows.append({
            "repeats": repeats,
            "layers": len(target),
            "stable": result["predecessorStable"],
            "relation": result["relation"],
            "helpersCraftable": all(result["helperCraftable"]),
            "predecessorCells": sum(ch != "-" for ch in str(result["predecessor"]) if ch != ":"),
        })
    return {"family": "S + (S-S-c)^n", "rows": rows}


def main() -> None:
    print(json.dumps({
        "schemaVersion": 1,
        "exhaustive": exhaustive(8),
        "highLayerFamily": family_audit(100),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
