from __future__ import annotations

import itertools
import random
import unittest

from stack_pp import (
    AnyTopPiecePolicy,
    PredicateTopPiecePolicy,
    RowInfo,
    StackClosureAutomaton,
    StackFamilyProductDAG,
)
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


class NoPinFamily:
    name = "no-pin"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        return None if row_signature[2] else state

    def accepts(self, state):
        return state == 0


class StackClosureAutomatonTests(unittest.TestCase):
    def _compare(self, rows, family, top_policy=None):
        direct = StackFamilyProductDAG(rows, family, top_policy).exists()
        closure = StackClosureAutomaton(family, top_policy).contains_rows(rows)
        self.assertEqual(closure, direct, rows)

    def test_exhaustive_one_layer_matches_target_dag(self):
        for cells in itertools.product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4):
            self._compare((RowInfo.from_cells(cells),), AllFamily())

    def test_random_multilayer_matches_target_dag(self):
        rng = random.Random(0x5A17C10)
        policies = (
            None,
            PredicateTopPiecePolicy(
                "no-visible-top-pin", lambda signature: signature[2] == 0
            ),
        )
        for layers in (2, 3, 4):
            for _ in range(350):
                rows = tuple(
                    RowInfo.from_cells(
                        rng.choices((EMPTY, NORMAL, PIN, CRYSTAL), k=4)
                    )
                    for _ in range(layers)
                )
                for family in (AllFamily(), NoPinFamily()):
                    for policy in policies:
                        self._compare(rows, family, policy)

    def test_closure_automaton_can_be_used_as_next_bottom_family(self):
        first = StackClosureAutomaton(AllFamily(), AnyTopPiecePolicy())
        rows = (
            RowInfo.from_cells((NORMAL, EMPTY, EMPTY, EMPTY)),
            RowInfo.from_cells((NORMAL, NORMAL, EMPTY, EMPTY)),
            RowInfo.from_cells((NORMAL, NORMAL, NORMAL, EMPTY)),
        )
        nested = StackFamilyProductDAG(rows, first)
        # The assertion is equivalence of the two public membership paths, not
        # a claim that this particular example must be accepted.
        self.assertEqual(
            nested.exists(),
            StackClosureAutomaton(first).contains_rows(rows),
        )


if __name__ == "__main__":
    unittest.main()
