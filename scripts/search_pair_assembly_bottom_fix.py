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
from backend.corner_half.corner_regions import Route, ZoneWitnessKind, analyze_column
from backend.corner_half.structural_physics import code, column, is_stable, push_pin
from scripts.audit_legacy_predecessor_all_layers import legacy_predecessor_rows

VALUES = ("-", "S", "c", "P")


def eligible_columns(max_len: int = 8) -> list[str]:
    out: list[str] = []
    for length in range(1, max_len + 1):
        for chars in itertools.product(ALPHABET, repeat=length):
            if chars[-1] == "-":
                continue
            target = "".join(chars)
            if "c" not in target or not is_craftable_column(target):
                continue
            witness = analyze_column(target)
            if witness.route is Route.EVENT and witness.zone and witness.zone.kind is ZoneWitnessKind.PAIR_ASSEMBLY:
                out.append(target)
    return out


def valid_exact(rows: list[list[str]], target: str) -> bool:
    if not is_stable(rows):
        return False
    if column(push_pin(rows, len(target)), 0) != target:
        return False
    return all(is_craftable_column(column(rows, q)) for q in range(4))


def mutations(rows: list[list[str]], max_changes: int = 3, window: int = 5):
    cap = len(rows)
    coordinates = [(l, q) for l in range(min(window, cap)) for q in (0, 3)]
    original = {(l, q): rows[l][q] for l, q in coordinates}
    for changes in range(1, max_changes + 1):
        for coords in itertools.combinations(coordinates, changes):
            alternatives = [[v for v in VALUES if v != original[pos]] for pos in coords]
            for values in itertools.product(*alternatives):
                candidate = [row.copy() for row in rows]
                delta = []
                for (l, q), value in zip(coords, values):
                    before = candidate[l][q]
                    candidate[l][q] = value
                    delta.append((l, q, before, value))
                yield candidate, tuple(delta)


def search_one(target: str) -> dict[str, object]:
    base = legacy_predecessor_rows(target, len(target))
    base_out = column(push_pin(base, len(target)), 0)
    if base_out == target:
        return {"target": target, "baseExact": True, "delta": [], "predecessor": code(base)}
    checked = 0
    for candidate, delta in mutations(base):
        checked += 1
        if valid_exact(candidate, target):
            return {
                "target": target,
                "baseExact": False,
                "baseOutput": base_out,
                "checked": checked,
                "delta": [list(item) for item in delta],
                "predecessor": code(candidate),
                "pillars": [column(candidate, q) for q in range(4)],
            }
    return {"target": target, "baseExact": False, "baseOutput": base_out, "checked": checked, "delta": None}


def main() -> None:
    targets = eligible_columns(8)
    results = [search_one(target) for target in targets]
    signatures = Counter()
    failures = []
    for result in results:
        delta = result.get("delta")
        if delta is None:
            failures.append(result)
            continue
        signature = tuple((item[0], item[1], item[2], item[3]) for item in delta)
        signatures[str(signature)] += 1

    family = []
    for repeats in list(range(1, 13)) + [16, 24, 32, 48, 64, 100]:
        target = "S" + "S-S-c" * repeats
        family.append({"repeats": repeats, "layers": len(target), **search_one(target)})

    print(json.dumps({
        "schemaVersion": 1,
        "search": {"window": 5, "maxChanges": 3, "values": VALUES},
        "exhaustiveTargets": len(targets),
        "solved": sum(result.get("delta") is not None for result in results),
        "failed": len(failures),
        "deltaSignatures": dict(signatures.most_common()),
        "failures": failures[:20],
        "examples": results[:32],
        "highLayerFamily": family,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
