from __future__ import annotations

import unittest

from stack_pp import (
    DifferenceLayerAutomaton,
    IntersectionLayerAutomaton,
    UnionLayerAutomaton,
    accepts_rows,
)


class ContainsPin:
    name = "contains-pin"

    def start_state(self):
        return False

    def advance(self, state, row):
        return state or bool(row[2])

    def accepts(self, state):
        return state


class ContainsCrystal:
    name = "contains-crystal"

    def start_state(self):
        return False

    def advance(self, state, row):
        return state or bool(row[1])

    def accepts(self, state):
        return state


class NoOrdinaryAfterPin:
    name = "no-ordinary-after-pin"

    def start_state(self):
        return False

    def advance(self, saw_pin, row):
        if saw_pin and row[3]:
            return None
        return saw_pin or bool(row[2])

    def accepts(self, state):
        return True


class AutomataAlgebraTests(unittest.TestCase):
    def setUp(self):
        self.pin = (1, 0, 1, 0)
        self.crystal = (1, 1, 0, 0)
        self.normal = (1, 0, 0, 1)

    def test_union(self):
        union = UnionLayerAutomaton((ContainsPin(), ContainsCrystal()))
        self.assertTrue(accepts_rows(union, (self.pin,)))
        self.assertTrue(accepts_rows(union, (self.crystal,)))
        self.assertFalse(accepts_rows(union, (self.normal,)))

    def test_intersection(self):
        both = IntersectionLayerAutomaton((ContainsPin(), ContainsCrystal()))
        self.assertTrue(accepts_rows(both, (self.pin, self.crystal)))
        self.assertFalse(accepts_rows(both, (self.pin,)))

    def test_difference_and_dead_right_state(self):
        pin_not_crystal = DifferenceLayerAutomaton(ContainsPin(), ContainsCrystal())
        self.assertTrue(accepts_rows(pin_not_crystal, (self.pin,)))
        self.assertFalse(accepts_rows(pin_not_crystal, (self.pin, self.crystal)))

        # Right side dies after pin->normal, but the left language continues.
        diff = DifferenceLayerAutomaton(ContainsPin(), NoOrdinaryAfterPin())
        self.assertTrue(accepts_rows(diff, (self.pin, self.normal)))


if __name__ == "__main__":
    unittest.main()
