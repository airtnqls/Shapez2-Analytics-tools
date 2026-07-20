from __future__ import annotations

import itertools
import unittest

from .corner_dfa import ALPHABET, is_craftable_column
from .corner_regions import Route, analyze_column
from .global_predecessor import GlobalRelation, compile_global_predecessor
from .structural_physics import column, parse, push_pin


class GlobalPredecessorTests(unittest.TestCase):
    def test_supplied_pair_assembly_family(self) -> None:
        target = "SS-S-cS-S-c"
        cert = compile_global_predecessor(target, len(target))
        self.assertTrue(cert.predecessor_stable)
        self.assertTrue(cert.helpers_all_craftable)
        self.assertEqual(cert.relation, GlobalRelation.BOTTOM_RECEIPT)
        self.assertEqual(cert.pushed_columns[0], "PS-S-cS-S-c")
        self.assertLessEqual(cert.inspections, 20 * len(target))

    def test_high_layer_family_is_linear_and_replayed(self) -> None:
        for repeats in (1, 2, 4, 8, 16, 32, 64, 100):
            target = "S" + "S-S-c" * repeats
            cert = compile_global_predecessor(target, len(target))
            self.assertTrue(cert.predecessor_stable)
            self.assertTrue(cert.helpers_all_craftable)
            self.assertEqual(cert.relation, GlobalRelation.BOTTOM_RECEIPT)
            self.assertEqual(column(push_pin(parse(cert.predecessor, len(target)), len(target)), 0), cert.pushed_columns[0])
            self.assertLessEqual(cert.inspections, 20 * len(target))

    def test_exhaustive_small_event_columns_are_stable_and_craftable(self) -> None:
        checked = exact = accepted = 0
        for length in range(1, 8):
            for chars in itertools.product(ALPHABET, repeat=length):
                if chars[-1] == "-":
                    continue
                target = "".join(chars)
                if "c" not in target or not is_craftable_column(target):
                    continue
                if analyze_column(target).route is not Route.EVENT:
                    continue
                accepted += 1
                cert = compile_global_predecessor(target, length)
                self.assertTrue(cert.predecessor_stable, target)
                self.assertTrue(cert.helpers_all_craftable, target)
                self.assertLessEqual(cert.inspections, 20 * length, target)
                checked += 1
                exact += cert.relation is GlobalRelation.EXACT
        self.assertEqual(checked, accepted)
        self.assertGreater(exact, 0)


if __name__ == "__main__":
    unittest.main()
