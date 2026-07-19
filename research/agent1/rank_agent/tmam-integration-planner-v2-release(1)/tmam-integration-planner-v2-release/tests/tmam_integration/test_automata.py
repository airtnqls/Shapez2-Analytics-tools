from __future__ import annotations

import unittest

from tmam import DFA, distinguishing_word, minimize_dfa, product_dfa


class AutomataTests(unittest.TestCase):
    def divisible_by_two_dfa(self):
        # Accept binary strings ending in 0. States 0 and 2 are equivalent;
        # states 1 and 3 are equivalent.
        alphabet = ("0", "1")
        states = frozenset({0, 1, 2, 3})
        transition = {
            (state, symbol): (0 if symbol == "0" else 1)
            for state in states
            for symbol in alphabet
        }
        return DFA(alphabet, states, 2, frozenset({0, 2}), transition)

    def test_minimization(self):
        result = minimize_dfa(self.divisible_by_two_dfa())
        self.assertEqual(len(result.dfa.states), 2)
        self.assertTrue(result.dfa.accepts("10"))
        self.assertFalse(result.dfa.accepts("11"))

    def test_equivalence_witness(self):
        left = self.divisible_by_two_dfa()
        minimized = minimize_dfa(left).dfa
        self.assertIsNone(distinguishing_word(left, minimized))

    def test_product(self):
        dfa = minimize_dfa(self.divisible_by_two_dfa()).dfa
        both = product_dfa(dfa, dfa, accept_when=lambda a, b: a and b)
        self.assertTrue(both.accepts("0"))
        self.assertFalse(both.accepts("1"))


if __name__ == "__main__":
    unittest.main()
