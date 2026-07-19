from __future__ import annotations

import itertools
import random
import unittest

from stack_pp import (
    AutomatonBuildLimitExceeded,
    LegacyStackClosureAutomaton,
    PredicateTopPiecePolicy,
    RowInfo,
    StackClosureAutomaton,
    StackFamilyProductDAG,
    compile_complete_minimized,
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


class CanonicalParityFamily:
    """Tiny family exercising canonicalization and exact inclusion hooks."""

    name = "parity"

    def start_state(self):
        return (0, "duplicate-tag")

    def canonical_state(self, state):
        return state[0] if isinstance(state, tuple) else state

    def advance(self, state, row_signature):
        return (self.canonical_state(state) ^ (row_signature[0].bit_count() & 1), "x")

    def accepts(self, state):
        return self.canonical_state(state) == 0

    def state_includes(self, left, right):
        return self.canonical_state(left) == self.canonical_state(right)


ROWS = tuple(
    RowInfo.from_cells(cells)
    for cells in itertools.product((EMPTY, NORMAL, PIN, CRYSTAL), repeat=4)
)


class OptimizedStackClosureTests(unittest.TestCase):
    def test_exhaustive_two_layers_matches_legacy(self):
        family = AllFamily()
        legacy = LegacyStackClosureAutomaton(family)
        optimized = StackClosureAutomaton(family)
        first_legacy = [
            legacy.advance(legacy.start_state(), row.as_signature()) for row in ROWS
        ]
        first_optimized = [
            optimized.advance(optimized.start_state(), row.as_signature()) for row in ROWS
        ]
        for lower_id, lower in enumerate(ROWS):
            for upper_id, upper in enumerate(ROWS):
                old_state = first_legacy[lower_id]
                new_state = first_optimized[lower_id]
                old_state = (
                    None
                    if old_state is None
                    else legacy.advance(old_state, upper.as_signature())
                )
                new_state = (
                    None
                    if new_state is None
                    else optimized.advance(new_state, upper.as_signature())
                )
                old_answer = old_state is not None and legacy.accepts(old_state)
                new_answer = new_state is not None and optimized.accepts(new_state)
                self.assertEqual(
                    old_answer,
                    new_answer,
                    (lower_id, upper_id, lower, upper),
                )

    def test_random_multilayer_legacy_and_target_dag(self):
        rng = random.Random(0x0A170A17)
        policies = (
            None,
            PredicateTopPiecePolicy(
                "no-visible-top-pin", lambda signature: signature[2] == 0
            ),
        )
        for family in (AllFamily(), NoPinFamily(), CanonicalParityFamily()):
            for policy in policies:
                legacy = LegacyStackClosureAutomaton(family, policy)
                optimized = StackClosureAutomaton(family, policy)
                for layers in range(1, 13):
                    for _ in range(180):
                        rows = tuple(rng.choice(ROWS) for _ in range(layers))
                        old_state = legacy.start_state()
                        new_state = optimized.start_state()
                        for row in rows:
                            old_state = (
                                None
                                if old_state is None
                                else legacy.advance(old_state, row.as_signature())
                            )
                            new_state = (
                                None
                                if new_state is None
                                else optimized.advance(new_state, row.as_signature())
                            )
                        old_answer = old_state is not None and legacy.accepts(old_state)
                        new_answer = new_state is not None and optimized.accepts(new_state)
                        direct = StackFamilyProductDAG(rows, family, policy).exists()
                        self.assertEqual(old_answer, new_answer)
                        self.assertEqual(new_answer, direct)

    def test_witness_is_a_real_target_dag_path(self):
        rng = random.Random(0xA11CE551)
        family = AllFamily()
        optimized = StackClosureAutomaton(family)
        for layers in range(1, 8):
            for _ in range(250):
                rows = tuple(rng.choice(ROWS) for _ in range(layers))
                witness = optimized.witness(rows)
                direct = StackFamilyProductDAG(rows, family)
                self.assertEqual(witness is not None, direct.exists())
                if witness is not None:
                    self.assertIn(witness.ownership_path, set(direct.iter_paths()))

    def test_action_groups_are_exact_partition(self):
        automaton = StackClosureAutomaton(AllFamily())
        exploration = automaton.explore(3)
        states = set().union(*exploration.levels)
        for state_id in states:
            groups = automaton.transition_groups(state_id)
            covered = 0
            for group in groups:
                self.assertEqual(covered & group.row_mask, 0)
                covered |= group.row_mask
                bits = group.row_mask
                while bits:
                    bit = bits & -bits
                    row_id = bit.bit_length() - 1
                    bits -= bit
                    self.assertEqual(
                        automaton.transition(state_id, row_id), group.next_state
                    )
            self.assertEqual(covered, (1 << 256) - 1)


    def test_family_canonicalization_is_applied_before_interning(self):
        optimized = StackClosureAutomaton(CanonicalParityFamily())
        state = optimized.start_state()
        for row in (
            RowInfo.from_cells((NORMAL, EMPTY, EMPTY, EMPTY)),
            RowInfo.from_cells((NORMAL, NORMAL, EMPTY, EMPTY)),
        ):
            state = optimized.advance(state, row.as_signature())
            self.assertIsNotNone(state)
        self.assertEqual(optimized.metrics().interned_family_states, 2)

    def test_diagnostic_build_limit_is_not_a_rejection(self):
        source = StackClosureAutomaton(AllFamily())
        with self.assertRaises(AutomatonBuildLimitExceeded):
            compile_complete_minimized(source, max_states=100)
        rows = (0, 85, 170, 255)
        # The same source remains a valid exact on-demand recognizer after the
        # caller-side compilation guard fired.
        self.assertEqual(source.accepts_rows(rows), source.witness(rows) is not None)

    def test_complete_minimization_preserves_membership_and_witness(self):
        source = StackClosureAutomaton(AllFamily())
        minimized = compile_complete_minimized(source)
        self.assertLess(minimized.metrics().minimized_states, minimized.metrics().source_states)
        rng = random.Random(0xDFA005)
        for layers in range(1, 30):
            for _ in range(200):
                rows = tuple(rng.randrange(256) for _ in range(layers))
                self.assertEqual(source.accepts_rows(rows), minimized.accepts_rows(rows))
                self.assertEqual(
                    source.witness(rows) is not None,
                    minimized.witness(rows) is not None,
                )


if __name__ == "__main__":
    unittest.main()
