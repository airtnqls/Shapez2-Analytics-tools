from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import (
    LegacyStackClosureAutomaton,
    RowInfo,
    StackClosureAutomaton,
    StackFamilyProductDAG,
)
from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN


class AllFamily:
    name = "all-stable-A"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        del row_signature
        return state

    def accepts(self, state):
        return True


def parse(code: str) -> tuple[RowInfo, ...]:
    mapping = {"-": EMPTY, "S": NORMAL, "P": PIN, "c": CRYSTAL}
    rows = [
        RowInfo.from_cells(mapping[ch] for ch in layer)
        for layer in code.strip().split(":")
    ]
    while rows and rows[-1].occupied == 0:
        rows.pop()
    return tuple(rows)


def legacy_accepts(automaton, rows) -> bool:
    state = automaton.start_state()
    for row in rows:
        state = automaton.advance(state, row.as_signature())
        if state is None:
            return False
    return automaton.accepts(state)


def main() -> int:
    source = Path(
        "/mnt/data/all40171clawsnohybrid_정렬됨_claw_complex_hybrid.txt"
    )
    lines = [
        line.strip()
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    family = AllFamily()
    legacy = LegacyStackClosureAutomaton(family)
    optimized = StackClosureAutomaton(family)
    failures = []
    witness_times = []
    membership_times = []
    path_counts = []
    started = time.perf_counter()

    for line_no, code in enumerate(lines, 1):
        rows = parse(code)
        old = legacy_accepts(legacy, rows)
        t0 = time.perf_counter_ns()
        new = optimized.accepts_rows(rows)
        membership_times.append(time.perf_counter_ns() - t0)
        t0 = time.perf_counter_ns()
        witness = optimized.witness(rows)
        witness_times.append(time.perf_counter_ns() - t0)
        direct = StackFamilyProductDAG(rows, family)
        path_counts.append(direct.path_count())
        actual_paths = set(direct.iter_paths())
        if (
            old != new
            or new != direct.exists()
            or new != (witness is not None)
            or (witness is not None and witness.ownership_path not in actual_paths)
        ):
            failures.append(
                {
                    "line": line_no,
                    "shape": code,
                    "legacy": old,
                    "optimized": new,
                    "direct": direct.exists(),
                    "witness": None if witness is None else witness.ownership_path,
                }
            )
            if len(failures) >= 20:
                break

    report = {
        "samples": len(lines),
        "legacy_optimized_direct_witness_mismatches": len(failures),
        "sample_failures": failures,
        "path_count_total": sum(path_counts),
        "path_count_min": min(path_counts, default=0),
        "path_count_max": max(path_counts, default=0),
        "membership_median_us": statistics.median(membership_times) / 1000.0,
        "witness_median_us": statistics.median(witness_times) / 1000.0,
        "seconds": time.perf_counter() - started,
    }
    out = ROOT / "reports" / "optimized_367_differential.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
