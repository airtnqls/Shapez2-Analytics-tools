from __future__ import annotations

import unittest

from tmam import AutomatonFamily, DFA, RankedFamilySequence


class FamilyAlgebraTests(unittest.TestCase):
    def family(self, family_id, accepts_zero):
        alphabet = ("0", "1")
        states = frozenset({0, 1})
        transition = {
            (0, "0"): 0,
            (0, "1"): 1,
            (1, "0"): 0,
            (1, "1"): 1,
        }
        accepting = frozenset({0}) if accepts_zero else frozenset({1})
        return AutomatonFamily(family_id, DFA(alphabet, states, 0, accepting, transition))

    def test_union_and_difference(self):
        zero = self.family("zero", True)
        one = self.family("one", False)
        all_family = zero.union(one, family_id="all")
        self.assertTrue(all_family.contains("0"))
        self.assertTrue(all_family.contains("1"))
        only_zero = all_family.difference(one, family_id="zero2")
        self.assertTrue(only_zero.contains("0"))
        self.assertFalse(only_zero.contains("1"))

    def test_rank_stabilization(self):
        sequence = RankedFamilySequence()
        sequence.append(0, self.family("zero0", True))
        stage = sequence.append(1, self.family("zero1", True))
        self.assertTrue(stage.stabilized_against_previous)
        self.assertIsNone(stage.counterexample)


if __name__ == "__main__":
    unittest.main()
