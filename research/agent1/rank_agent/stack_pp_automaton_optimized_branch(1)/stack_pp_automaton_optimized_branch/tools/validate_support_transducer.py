from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN, ADJACENT, RowInfo
from stack_pp.stack_product import (
    _EMPTY_SUPPORT_BEHAVIOR,
    _advance_support_behavior,
    _support_behavior_accepts,
)


def stable(rows: tuple[RowInfo, ...]) -> bool:
    occupied = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.occupied & (1 << q)}
    crystal = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.crystal & (1 << q)}
    pin = {(l, q) for l, row in enumerate(rows) for q in range(4) if row.pin & (1 << q)}
    supported = {(0, q) for q in range(4) if (0, q) in occupied}
    while True:
        before = set(supported)
        for l, q in occupied:
            if l > 0 and (l - 1, q) in supported:
                supported.add((l, q))
            if (l, q) not in pin:
                for nq in ADJACENT[q]:
                    if (l, nq) in supported and (l, nq) not in pin:
                        supported.add((l, q))
            if (l, q) in crystal and (l + 1, q) in supported and (l + 1, q) in crystal:
                supported.add((l, q))
        if supported == before:
            return supported == occupied


def main() -> int:
    all_rows = [RowInfo.from_cells(cells) for cells in itertools.product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4)]
    mismatches = []
    start = time.perf_counter()
    for r0 in all_rows:
        b0 = _advance_support_behavior(
            _EMPTY_SUPPORT_BEHAVIOR,
            0,
            0,
            r0.occupied,
            r0.crystal,
            r0.pin,
            True,
        )
        for r1 in all_rows:
            b1 = _advance_support_behavior(
                b0,
                r0.occupied,
                r0.crystal,
                r1.occupied,
                r1.crystal,
                r1.pin,
                False,
            )
            actual = _support_behavior_accepts(b1, r1.occupied)
            expected = stable((r0, r1))
            if actual != expected and len(mismatches) < 20:
                mismatches.append({
                    "r0": r0.as_signature(),
                    "r1": r1.as_signature(),
                    "expected": expected,
                    "actual": actual,
                })
    report = {
        "row_pairs": len(all_rows) ** 2,
        "mismatches": len(mismatches),
        "sample_mismatches": mismatches,
        "seconds": time.perf_counter() - start,
    }
    out = ROOT / "reports" / "support_transducer_exhaustive.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
