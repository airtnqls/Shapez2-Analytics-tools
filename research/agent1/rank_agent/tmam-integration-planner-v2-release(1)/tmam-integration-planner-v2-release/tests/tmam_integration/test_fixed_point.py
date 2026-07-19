from __future__ import annotations

import unittest

from tmam import least_fixed_point


class FixedPointTests(unittest.TestCase):
    def test_closure(self):
        def expand(current):
            result = set(current)
            for value in current:
                if value < 5:
                    result.add(value + 1)
            return result

        result = least_fixed_point({0}, expand)
        self.assertEqual(result.value, frozenset(range(6)))
        self.assertEqual(result.rounds[-1].added, frozenset())

    def test_rejects_non_inflationary_transfer(self):
        with self.assertRaises(ValueError):
            least_fixed_point({1}, lambda _current: set())


if __name__ == "__main__":
    unittest.main()
