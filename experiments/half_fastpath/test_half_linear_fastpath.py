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
from optimizer_suite import (
    benchmark as benchmark_suite,
    delta_proof_storage,
    eager_proof_storage,
    linear_stack_boundary,
    naive_stack_split,
)


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

    def test_stack_split_one_pass_beats_all_split_materialization(self) -> None:
        for layers in (32, 64, 128, 256, 512):
            rows = tuple("SS" if i < layers // 2 else "cS" for i in range(layers))
            slow = naive_stack_split(rows)
            fast = linear_stack_boundary(rows)
            self.assertEqual(fast.candidates, 1)
            self.assertGreater(slow.candidates, fast.candidates)
            self.assertGreater(slow.inspections, fast.inspections)
            self.assertLessEqual(fast.inspections, layers)

    def test_delta_proof_ir_avoids_quadratic_shape_storage(self) -> None:
        previous_delta = None
        for layers in (32, 64, 128, 256, 512):
            operations = max(4, layers // 2)
            eager = eager_proof_storage(layers, operations)
            delta = delta_proof_storage(layers, 2, operations)
            self.assertLess(delta.materialized_cells, eager.materialized_cells)
            if previous_delta is not None:
                self.assertLessEqual(delta.materialized_cells, previous_delta * 2 + 16)
            previous_delta = delta.materialized_cells

    def test_cross_cutting_benchmark_is_reproducible(self) -> None:
        report = benchmark_suite()
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(len(report["rows"]), 6)
        for row in report["rows"]:
            self.assertGreater(row["stack_inspection_reduction"], 0.90)
            self.assertGreater(row["proof_cell_reduction"], 0.80)
            self.assertLessEqual(row["event_gap_bound_ratio"], 2.2)

    def test_benchmark_json_is_reproducible(self) -> None:
        report = benchmark(128)
        encoded = json.dumps(report, sort_keys=True)
        self.assertIn('"fast_nodes"', encoded)
        self.assertIn('"node_reduction"', encoded)


if __name__ == "__main__":
    unittest.main()
