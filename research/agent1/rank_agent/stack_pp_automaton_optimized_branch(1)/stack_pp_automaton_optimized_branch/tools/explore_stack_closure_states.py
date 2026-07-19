from __future__ import annotations

import argparse
import json
import time
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import RowInfo, StackClosureAutomaton
from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN


class AllFamily:
    name = "all-stable-base"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        del row_signature
        return state

    def accepts(self, state):
        return state == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "reports"
        / "stack_closure_state_growth.json",
    )
    args = parser.parse_args()
    alphabet = tuple(
        RowInfo.from_cells(cells).as_signature()
        for cells in product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4)
    )
    automaton = StackClosureAutomaton(AllFamily())
    t0 = time.perf_counter()
    levels = automaton.reachable_states(alphabet, args.depth)
    elapsed = time.perf_counter() - t0
    report = {
        "base_family": "all-stable-base",
        "alphabet_rows": len(alphabet),
        "max_depth": args.depth,
        "reachable_states_per_exact_depth": [len(level) for level in levels],
        "accepting_states_per_exact_depth": [
            sum(automaton.accepts(state) for state in level) for level in levels
        ],
        "max_product_subset_size_per_depth": [
            max((len(state.product_states) for state in level), default=0)
            for level in levels
        ],
        "transition_cache_entries": len(automaton._transition_cache),
        "seconds": elapsed,
        "interpretation": (
            "Finite powerset closure is proved; these counts measure only "
            "reachable-state growth for the universal base family and are not "
            "a proof that rank iteration stays small."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
