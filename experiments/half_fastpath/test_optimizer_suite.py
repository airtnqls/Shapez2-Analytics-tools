from __future__ import annotations

import unittest

from optimizer_suite import (
    delta_proof_storage,
    eager_proof_storage,
    event_gap_suffix,
    lazy_materialization_cost,
    linear_stack_boundary,
    make_event_word,
    mode_separated_work,
    naive_repeated_suffix,
    naive_stack_split,
)


class OptimizerSuiteTests(unittest.TestCase):
    def test_event_gap_recognizer_matches_reference(self) -> None:
        for layers in (21, 41, 81, 161):
            word = make_event_word(layers)
            fast = event_gap_suffix(word)
            slow = naive_repeated_suffix(word)
            self.assertIsNotNone(fast)
            self.assertIsNotNone(slow)
            assert fast is not None and slow is not None
            self.assertEqual(fast[:2], slow)
            self.assertLessEqual(fast[2], 3 * layers)

    def test_event_gap_rejects_mutation(self) -> None:
        word = list(make_event_word(81))
        word[37] = "P"
        self.assertIsNone(event_gap_suffix(word))

    def test_unique_stack_boundary_is_linear_and_single_candidate(self) -> None:
        rows = tuple("SS" if i < 100 else "cS" for i in range(200))
        slow = naive_stack_split(rows)
        fast = linear_stack_boundary(rows)
        self.assertEqual(fast.candidates, 1)
        self.assertEqual(fast.inspections, len(rows))
        self.assertLess(fast.inspections, slow.inspections // 50)
        self.assertLess(fast.materialized_cells, slow.materialized_cells // 50)

    def test_ambiguous_stack_falls_back(self) -> None:
        rows = ("SS", "cS", "SS", "cS")
        fast = linear_stack_boundary(rows)
        self.assertEqual(fast.candidates, 0)

    def test_delta_proof_storage_reduces_cells(self) -> None:
        eager = eager_proof_storage(200, 100)
        delta = delta_proof_storage(200, 2, 100)
        self.assertLess(delta.materialized_cells, eager.materialized_cells // 20)

    def test_lazy_view_materializes_only_opened_nodes(self) -> None:
        eager, lazy = lazy_materialization_cost(200, 100, opened_nodes=3)
        self.assertLess(lazy, eager // 20)

    def test_mode_separation_is_strict(self) -> None:
        work = mode_separated_work(100, 20)
        self.assertLess(work["verdict"], work["analysis"])
        self.assertLess(work["analysis"], work["proof"])


if __name__ == "__main__":
    unittest.main()
