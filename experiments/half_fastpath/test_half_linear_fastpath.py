from __future__ import annotations

import json
import random
import unittest

from half_linear_fastpath import (
    TARGET,
    baseline_recursive_dag,
    benchmark,
    compile_linear_half,
    fast_linear_dag,
    make_family,
    parse_shape,
    replay_structural,
    structural_rows,
)
from optimizer_suite import benchmark_suite, delta_proof_stats, eager_proof_stats, fast_feature_dispatch, generic_candidate_planner


class HalfLinearFastPathTests(unittest.TestCase):
    def test_supplied_target_is_recognized_and_replayed(self) -> None:
        program = compile_linear_half(TARGET)
        self.assertIsNotNone(program)
        assert program is not None
        self.assertEqual(program.subtype, "HALF_PERIODIC_PIN_SWAP")
        self.assertEqual(program.repeats, 2)
        self.assertEqual(program.block, ("S", "-", "S", "-", "c"))
        self.assertEqual(replay_structural(program), structural_rows(parse_shape(TARGET)))

    def test_actual_dag_metrics_drop_on_supplied_target(self) -> None:
        baseline = baseline_recursive_dag(TARGET)
        fast = fast_linear_dag(TARGET)
        self.assertIsNotNone(fast)
        assert fast is not None
        self.assertLess(fast.nodes, baseline.nodes)
        self.assertLess(fast.edges, baseline.edges)
        self.assertLess(fast.operations, baseline.operations)
        self.assertLess(fast.materialized_row_cells, baseline.materialized_row_cells)
        self.assertGreaterEqual(1.0 - fast.nodes / baseline.nodes, 0.50)
        self.assertGreaterEqual(1.0 - fast.materialized_row_cells / baseline.materialized_row_cells, 0.45)

    def test_scan_bound_is_linear(self) -> None:
        for repeats in (2, 4, 8, 16, 32, 64, 128, 256):
            code = make_family(repeats)
            program = compile_linear_half(code)
            self.assertIsNotNone(program)
            assert program is not None
            layers = len(parse_shape(code))
            self.assertLessEqual(program.inspected_rows, 2 * layers)

    def test_node_growth_is_linear_and_baseline_is_quadratic(self) -> None:
        previous_fast = None
        for repeats in (4, 8, 16, 32, 64, 128):
            code = make_family(repeats)
            baseline = baseline_recursive_dag(code)
            fast = fast_linear_dag(code)
            self.assertIsNotNone(fast)
            assert fast is not None
            if previous_fast is not None:
                self.assertLessEqual(fast.nodes, previous_fast * 2 + 4)
            previous_fast = fast.nodes
            self.assertGreater(baseline.nodes / fast.nodes, repeats / 8)

    def test_mutations_are_not_overmatched(self) -> None:
        rng = random.Random(20260719)
        base = make_family(8).split(":")
        rejected = 0
        for _ in range(200):
            rows = list(base)
            idx = rng.randrange(1, len(rows))
            old = rows[idx]
            choices = ["Su------", "----Su--", "--cw----", "--------"]
            rows[idx] = rng.choice([x for x in choices if x != old])
            if compile_linear_half(":".join(rows)) is None:
                rejected += 1
        self.assertEqual(rejected, 200)

    def test_generic_candidate_loop_vs_constant_fast_dispatch(self) -> None:
        for layers in (32, 64, 128, 256, 512):
            slow = generic_candidate_planner(layers)
            fast = fast_feature_dispatch(layers)
            self.assertGreater(slow.candidates, fast.candidates)
            self.assertGreater(slow.inspections, fast.inspections)
            self.assertLessEqual(fast.inspections, 6 * layers)
            self.assertLessEqual(fast.candidates, 6)

    def test_delta_proof_ir_avoids_quadratic_shape_storage(self) -> None:
        previous_delta = None
        for layers in (32, 64, 128, 256, 512):
            eager = eager_proof_stats(layers)
            delta = delta_proof_stats(layers)
            self.assertLess(delta.materialized_cells, eager.materialized_cells)
            self.assertLess(delta.proof_nodes, eager.proof_nodes)
            if previous_delta is not None:
                self.assertLessEqual(delta.materialized_cells, previous_delta * 2 + 16)
            previous_delta = delta.materialized_cells

    def test_cross_cutting_benchmark_is_reproducible(self) -> None:
        report = benchmark_suite()
        self.assertEqual(report["schema"], 1)
        self.assertEqual(len(report["rows"]), 5)
        for row in report["rows"]:
            self.assertGreater(row["candidate_reduction"], 0.99)
            self.assertGreater(row["cell_reduction"], 0.90)

    def test_benchmark_json_is_reproducible(self) -> None:
        report = benchmark(128)
        encoded = json.dumps(report, sort_keys=True)
        self.assertIn('"fast_nodes"', encoded)
        self.assertIn('"node_reduction"', encoded)


if __name__ == "__main__":
    unittest.main()
