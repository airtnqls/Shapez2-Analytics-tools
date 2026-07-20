from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import is_craftable_column
from backend.corner_half.global_predecessor import compile_global_predecessor
from backend.corner_half.structural_physics import EMPTY, code, column, is_stable, push_pin


def rows_from_columns(values: tuple[str, str, str, str], cap: int):
    return [
        [values[q][layer] if layer < len(values[q]) else EMPTY for q in range(4)]
        for layer in range(cap)
    ]


def compact_before_first_crystal(target: str) -> str:
    """Complete the unfinished legacy build_pinable_shape2 A-column rule."""
    low_c = target.find("c")
    if low_c < 0:
        raise ValueError("event target has no crystal")
    count_s = target[:low_c].count("S")
    a = list(target)
    placed = 0
    for layer in range(low_c - 1, -1, -1):
        if placed < count_s:
            a[layer] = "S"
            placed += 1
        else:
            a[layer] = EMPTY
    return "".join(a)


def search(target: str, *, alphabet: str = "-SP", max_hits: int = 20) -> dict:
    cap = len(target)
    first = compile_global_predecessor(target, cap)
    a1 = first.pushed_columns[0]
    a2 = compact_before_first_crystal(target)
    checked = craftable = half_stable = full_stable = 0
    hits: list[dict[str, object]] = []

    # B is a helper column, so trailing '-' variants are represented by shorter
    # words.  Enumerating fixed width is still convenient; normalize by rstrip.
    seen: set[str] = set()
    for cells in itertools.product(alphabet, repeat=cap):
        b = "".join(cells).rstrip(EMPTY)
        if b in seen:
            continue
        seen.add(b)
        checked += 1
        if not is_craftable_column(b):
            continue
        craftable += 1
        half = rows_from_columns((a2, b, "", ""), cap)
        if not is_stable(half):
            continue
        half_stable += 1
        full = rows_from_columns((a2, b, "", a1), cap)
        if not is_stable(full):
            continue
        full_stable += 1
        out = push_pin(full, cap)
        if column(out, 0) != target:
            continue
        hits.append({
            "b": b,
            "preFinal": code(full),
            "preFinalPillars": [column(full, q) for q in range(4)],
            "afterFinalPin": code(out),
            "afterFinalPillars": [column(out, q) for q in range(4)],
        })
        if len(hits) >= max_hits:
            break

    return {
        "target": target,
        "cap": cap,
        "firstPredecessor": first.predecessor,
        "afterFirstPin": first.pushed,
        "a1": a1,
        "a2": a2,
        "alphabet": alphabet,
        "checked": checked,
        "craftable": craftable,
        "halfStable": half_stable,
        "fullStable": full_stable,
        "hits": hits,
    }


def main() -> None:
    targets = [
        "SS-S-c",
        "SS-S-cS-S-c",
        "SS-S-cS-S-cS-S-c",
    ]
    reports = []
    for target in targets:
        # Full 3^L is fine for L<=11.  The longer family is tested only after a
        # reusable B rule has been inferred from the first two exact searches.
        if len(target) > 11:
            reports.append({"target": target, "skipped": "await inferred helper rule"})
            continue
        reports.append(search(target))
    print(json.dumps({"schemaVersion": 1, "reports": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
