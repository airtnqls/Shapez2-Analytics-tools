from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.corner_half.corner_dfa import ALPHABET, is_craftable_column
from backend.corner_half.corner_regions import Route, analyze_column
from backend.corner_half.global_predecessor import compile_global_predecessor
from backend.corner_half.structural_physics import code, column, push_pin
from scripts.audit_legacy_predecessor_all_layers import legacy_predecessor_rows


def main() -> None:
    checked = 0
    mismatches = []
    max_ratio = 0.0
    for length in range(1, 8):
        for chars in itertools.product(ALPHABET, repeat=length):
            if chars[-1] == "-":
                continue
            target = "".join(chars)
            if "c" not in target or not is_craftable_column(target):
                continue
            if analyze_column(target).route is not Route.EVENT:
                continue
            checked += 1
            legacy_rows = legacy_predecessor_rows(target, length)
            cert = compile_global_predecessor(target, length)
            max_ratio = max(max_ratio, cert.inspections / length)
            expected_predecessor = code(legacy_rows)
            expected_pushed_a = column(push_pin(legacy_rows, length), 0)
            if cert.predecessor != expected_predecessor or cert.pushed_columns[0] != expected_pushed_a:
                mismatches.append({
                    "target": target,
                    "expectedPredecessor": expected_predecessor,
                    "actualPredecessor": cert.predecessor,
                    "expectedPushedA": expected_pushed_a,
                    "actualPushedA": cert.pushed_columns[0],
                    "inspections": cert.inspections,
                })
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    family = []
    for repeats in (1, 2, 4, 8, 16, 32, 64, 100):
        target = "S" + "S-S-c" * repeats
        cert = compile_global_predecessor(target, len(target))
        family.append({
            "repeats": repeats,
            "layers": len(target),
            "relation": cert.relation.value,
            "stable": cert.predecessor_stable,
            "craftable": cert.helpers_all_craftable,
            "inspections": cert.inspections,
            "ratio": cert.inspections / len(target),
        })
    print(json.dumps({
        "checked": checked,
        "mismatches": mismatches,
        "maxInspectionRatio": max_ratio,
        "family": family,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
