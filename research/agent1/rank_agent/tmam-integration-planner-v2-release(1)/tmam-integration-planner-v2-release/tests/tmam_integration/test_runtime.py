from __future__ import annotations

import unittest

from tmam import (
    Goal,
    IntegrationRegistry,
    Operation,
    PlannerConfig,
    Progress,
    TMAMPlanner,
    TMAMRuntime,
)

from fakes import CertificateForwardModel, StringBackend, standard_relations


class RuntimeTests(unittest.TestCase):
    def test_end_to_end_analysis(self):
        relations = standard_relations()
        registry = IntegrationRegistry()
        for relation in relations:
            registry.register_relation(relation)
        planner = TMAMPlanner(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            registry=registry,
            config=PlannerConfig(frozenset(r.provider_id for r in relations)),
        )
        runtime = TMAMRuntime(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            planner=planner,
        )
        result = runtime.analyze("PAB", Progress((3,)))
        self.assertIsNotNone(result.analysis.solve.proof)
        self.assertIsNotNone(result.proof_validation)
        assert result.proof_validation is not None
        self.assertTrue(result.proof_validation.valid)

    def test_runtime_analysis_cache_tracks_planner_manual_invalidation(self):
        from test_planner_modes import LazyRelation, make_planner

        relation = LazyRelation("input.runtime.invalidate", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        runtime = TMAMRuntime(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            planner=planner,
        )

        first = runtime.analyze_all_ops("X", Progress((1,)))
        second = runtime.analyze_all_ops("X", Progress((1,)))
        self.assertIs(first, second)
        self.assertEqual(relation.inverse_calls, 1)

        planner.invalidate_provider(relation.provider_id)
        third = runtime.analyze_all_ops("X", Progress((1,)))
        self.assertIsNot(first, third)
        self.assertEqual(relation.inverse_calls, 2)



if __name__ == "__main__":
    unittest.main()
