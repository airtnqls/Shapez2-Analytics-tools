from __future__ import annotations

import unittest

from tmam import (
    CostVector,
    Goal,
    IntegrationRegistry,
    Operation,
    PlannerConfig,
    PlannerContractError,
    Progress,
    ProofStatus,
    ProofValidator,
    TMAMPlanner,
)

from fakes import CertificateForwardModel, StringBackend, TableRelation, standard_relations


class PlannerTests(unittest.TestCase):
    def make_planner(self, relations=None):
        registry = IntegrationRegistry()
        relations = relations or standard_relations()
        for relation in relations:
            registry.register_relation(relation)
        config = PlannerConfig(required_relation_ids=frozenset(r.provider_id for r in relations))
        return TMAMPlanner(backend=StringBackend(), forward=CertificateForwardModel(), registry=registry, config=config)

    def test_builds_ranked_pin_push_proof(self):
        planner = self.make_planner()
        result = planner.solve(Goal("PAB", Progress((3,))))
        self.assertEqual(result.status, ProofStatus.POSSIBLE)
        self.assertIsNotNone(result.proof)
        assert result.proof is not None
        self.assertEqual(result.proof.operation, Operation.PIN_PUSH)
        self.assertEqual(result.proof.children[0].operation, Operation.STACK)
        self.assertEqual(result.proof.total_cost.operations, 2)
        self.assertEqual(result.proof.total_cost.inputs, 2)
        report = ProofValidator(StringBackend(), CertificateForwardModel()).validate(result.proof)
        self.assertTrue(report.valid, report.issues)

    def test_impossible_requires_complete_coverage(self):
        planner = self.make_planner()
        result = planner.solve(Goal("Z", Progress((3,))))
        self.assertEqual(result.status, ProofStatus.IMPOSSIBLE)
        self.assertTrue(result.complete)

    def test_partial_provider_prevents_impossible_claim(self):
        relations = list(standard_relations())
        relations[0].complete = False
        planner = self.make_planner(relations)
        result = planner.solve(Goal("Z", Progress((3,))))
        self.assertEqual(result.status, ProofStatus.UNKNOWN)
        self.assertFalse(result.complete)

    def test_non_decreasing_child_is_rejected(self):
        relations = list(standard_relations())
        bad = TableRelation(
            "bad.loop",
            Operation.STACK,
            {
                "LOOP": (
                    (
                        (("LOOP", (3,), "bad"),),
                        CostVector(operations=1),
                        frozenset(),
                        {},
                    ),
                ),
            },
            priority=1,
        )
        relations.append(bad)
        planner = self.make_planner(relations)
        with self.assertRaises(PlannerContractError):
            planner.solve(Goal("LOOP", Progress((3,))))

    def test_progress_dimension_mismatch_is_rejected(self):
        relations = list(standard_relations())
        bad = TableRelation(
            "bad.dimension",
            Operation.STACK,
            {
                "DIM": (
                    (
                        (("A", (1, 0), "bad"),),
                        CostVector(operations=1),
                        frozenset(),
                        {},
                    ),
                ),
            },
            priority=1,
        )
        relations.append(bad)
        planner = self.make_planner(relations)
        with self.assertRaises(PlannerContractError):
            planner.solve(Goal("DIM", Progress((3,))))

    def test_operation_analysis(self):
        planner = self.make_planner()
        analysis = planner.analyze(Goal("AB", Progress((2,))))
        self.assertEqual(analysis.operations[Operation.STACK].possible, True)
        self.assertEqual(analysis.operations[Operation.PIN_PUSH].possible, False)
        self.assertEqual(analysis.possible_last_operations, frozenset({Operation.STACK}))

    def test_cheapest_candidate_wins(self):
        relations = list(standard_relations())
        direct = TableRelation(
            "input.expensive_ab",
            Operation.INPUT,
            {
                "AB": (
                    (
                        (),
                        CostVector(operations=10, inputs=1),
                        frozenset({"basic"}),
                        {},
                    ),
                ),
            },
            priority=1,
        )
        relations.append(direct)
        planner = self.make_planner(relations)
        result = planner.solve(Goal("AB", Progress((2,))))
        assert result.proof is not None
        self.assertEqual(result.proof.operation, Operation.STACK)
        self.assertEqual(result.proof.total_cost.operations, 1)


if __name__ == "__main__":
    unittest.main()
