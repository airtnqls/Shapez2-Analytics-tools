from __future__ import annotations

"""Exhaustively validate the optimized product simulation on its complete graph."""

from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack_pp import StackClosureAutomaton, compile_complete_minimized
from stack_pp.row_table import ROW_COUNT


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
    automaton = StackClosureAutomaton(AllFamily())
    compiled = compile_complete_minimized(
        automaton, release_source_build_caches=False
    )
    triples: set[tuple[int, int, int]] = set()
    # Recreate the raw powerset before antichain normalization for every
    # reachable deterministic state/row.  Record each actually removed product
    # together with one surviving simulator.
    for state in automaton._states[1:]:
        assert state is not None
        for row_id in range(ROW_COUNT):
            raw = {
                packed >> 4
                for product_id in state.products
                for packed in automaton._component_edges(
                    product_id, state.previous_occupied, row_id
                )
            }
            if len(raw) < 2:
                continue
            normalized = automaton._normalize_products(raw)
            normalized_set = set(normalized)
            for right in raw - normalized_set:
                left = next(
                    (
                        candidate
                        for candidate in normalized
                        if automaton._product_includes(candidate, right)
                    ),
                    None,
                )
                if left is not None:
                    triples.add((automaton._states[automaton.transition(
                        automaton._state_ids[state], row_id
                    )].previous_occupied, left, right))

    failures = []
    transition_obligations = 0
    t0 = time.perf_counter()
    for previous_occupied, left, right in sorted(triples):
        if automaton._product_accepts(right) and not automaton._product_accepts(left):
            failures.append(
                {
                    "kind": "terminal",
                    "previous_occupied": previous_occupied,
                    "left": left,
                    "right": right,
                }
            )
            break
        for row_id in range(ROW_COUNT):
            left_targets = tuple(
                packed >> 4
                for packed in automaton._component_edges(
                    left, previous_occupied, row_id
                )
            )
            right_targets = tuple(
                packed >> 4
                for packed in automaton._component_edges(
                    right, previous_occupied, row_id
                )
            )
            for right_target in right_targets:
                transition_obligations += 1
                if not any(
                    automaton._product_includes(left_target, right_target)
                    for left_target in left_targets
                ):
                    failures.append(
                        {
                            "kind": "step",
                            "previous_occupied": previous_occupied,
                            "left": left,
                            "right": right,
                            "row_id": row_id,
                            "left_targets": left_targets,
                            "right_target": right_target,
                        }
                    )
                    break
            if failures:
                break
        if failures:
            break

    report = {
        "complete_source_states": compiled.metrics().source_states,
        "unique_product_simulation_triples": len(triples),
        "transition_obligations_checked": transition_obligations,
        "failures": failures,
        "seconds": time.perf_counter() - t0,
        "scope": (
            "Complete reachable universal-base Stack product. Family-state "
            "subsumption is equality here; the switched/support simulation "
            "lemma is independent of the concrete family implementation."
        ),
    }
    out = ROOT / "reports" / "product_subsumption_exhaustive.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
