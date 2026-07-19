from __future__ import annotations

import unittest

from tmam import (
    Goal,
    IntegrationRegistry,
    PlannerConfig,
    Progress,
    TMAMPlanner,
    audit_relation,
    collect_proof_metrics,
)

from fakes import CertificateForwardModel, StringBackend, standard_relations


class MetricsAndTestkitTests(unittest.TestCase):
    def test_metrics_and_relation_audit(self):
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
        result = planner.solve(Goal("PAB", Progress((3,))))
        assert result.proof is not None
        metrics = collect_proof_metrics(result.proof)
        self.assertEqual(metrics.operation_counts["input"], 2)
        self.assertEqual(metrics.stack_depth, 1)
        pp = next(r for r in relations if r.provider_id == "pinpush.rank")
        report = audit_relation(
            pp,
            Goal("PAB", Progress((3,))),
            backend=StringBackend(),
            forward=CertificateForwardModel(),
        )
        self.assertTrue(report.valid, report.issues)
        self.assertEqual(report.candidate_count, 1)


if __name__ == "__main__":
    unittest.main()
