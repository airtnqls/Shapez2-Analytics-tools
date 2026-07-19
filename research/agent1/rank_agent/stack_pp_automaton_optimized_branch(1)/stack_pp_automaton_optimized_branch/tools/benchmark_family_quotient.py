from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import StackClosureAutomaton


class TaggedParityNoQuotient:
    name = "tagged-parity-no-quotient"

    def start_state(self):
        return (0, 0)

    def advance(self, state, row_signature):
        parity, tag = state
        return (parity ^ (row_signature[0].bit_count() & 1), tag ^ 1)

    def accepts(self, state):
        return state[0] == 0


class TaggedParityWithQuotient(TaggedParityNoQuotient):
    name = "tagged-parity-with-proved-quotient"

    def canonical_state(self, state):
        return state[0] if isinstance(state, tuple) else state

    def advance(self, state, row_signature):
        parity = self.canonical_state(state)
        return (parity ^ (row_signature[0].bit_count() & 1), 0)

    def accepts(self, state):
        return self.canonical_state(state) == 0

    def state_includes(self, left, right):
        return self.canonical_state(left) == self.canonical_state(right)


def run(family, depth: int) -> dict:
    automaton = StackClosureAutomaton(family)
    t0 = time.perf_counter()
    exploration = automaton.explore(depth)
    metrics = automaton.metrics()
    return {
        "family": family.name,
        "states_per_exact_depth": list(exploration.states_per_exact_depth),
        "cumulative_states_per_depth": list(exploration.cumulative_states_per_depth),
        "interned_family_states": metrics.interned_family_states,
        "reachable_states": metrics.reachable_states,
        "transitions": metrics.transitions,
        "memory_bytes": metrics.memory_bytes,
        "seconds": time.perf_counter() - t0,
    }


def main() -> int:
    report = {
        "depth": 3,
        "without_quotient": run(TaggedParityNoQuotient(), 3),
        "with_exact_quotient": run(TaggedParityWithQuotient(), 3),
        "proof_scope": (
            "The tag is deliberately semantically inert; canonical_state and "
            "state_includes are exact residual-language equivalences."
        ),
    }
    out = ROOT / "reports" / "family_quotient_benchmark.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
