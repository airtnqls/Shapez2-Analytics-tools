from __future__ import annotations

import json
import sys
import time
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import RowInfo, StackClosureAutomaton, StackFamilyProductDAG
from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN


class AllFamily:
    name = "all"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        del row_signature
        return state

    def accepts(self, state):
        return state == 0


def main() -> int:
    rows = tuple(
        RowInfo.from_cells(cells)
        for cells in product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4)
    )
    closure = StackClosureAutomaton(AllFamily())
    mismatches = []
    accepted_closure = 0
    accepted_target_dag = 0
    t0 = time.perf_counter()
    for lower in rows:
        state1 = closure.advance(closure.start_state(), lower.as_signature())
        for upper in rows:
            target_rows = (lower, upper)
            expected = StackFamilyProductDAG(target_rows, AllFamily()).exists()
            actual = False
            if state1 is not None:
                state2 = closure.advance(state1, upper.as_signature())
                actual = state2 is not None and closure.accepts(state2)
            accepted_target_dag += int(expected)
            accepted_closure += int(actual)
            if expected != actual and len(mismatches) < 20:
                mismatches.append(
                    {
                        "lower": lower.as_signature(),
                        "upper": upper.as_signature(),
                        "target_dag": expected,
                        "closure_automaton": actual,
                    }
                )
    report = {
        "targets_L2": len(rows) ** 2,
        "accepted_target_dag": accepted_target_dag,
        "accepted_closure_automaton": accepted_closure,
        "mismatches": len(mismatches),
        "sample_mismatches": mismatches,
        "transition_cache_entries": len(closure._transition_cache),
        "seconds": time.perf_counter() - t0,
    }
    out = ROOT / "reports" / "stack_closure_exhaustive_L2.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
