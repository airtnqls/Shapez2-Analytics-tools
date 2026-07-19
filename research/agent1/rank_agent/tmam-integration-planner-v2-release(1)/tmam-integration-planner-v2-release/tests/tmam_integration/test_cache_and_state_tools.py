from __future__ import annotations

import unittest

from tmam import (
    AutomatonMetrics,
    DFA,
    FamilyContext,
    Goal,
    IntegrationRegistry,
    Operation,
    PlannerConfig,
    Progress,
    StateInterner,
    TMAMPlanner,
    automaton_metrics,
)

from fakes import CertificateForwardModel, StringBackend, TableRelation


class CacheAndStateToolTests(unittest.TestCase):
    def test_state_interner_dense_ids(self):
        interner = StateInterner()
        self.assertEqual(interner.intern((1, 2)), 0)
        self.assertEqual(interner.intern((1, 2)), 0)
        self.assertEqual(interner.intern((2, 3)), 1)
        self.assertEqual(interner.states, ((1, 2), (2, 3)))

    def test_automaton_metrics(self):
        dfa = DFA(
            alphabet=("0", "1"),
            states=frozenset({0, 1, 2}),
            start=0,
            accepting=frozenset({1}),
            transition={
                (0, "0"): 0,
                (0, "1"): 1,
                (1, "0"): 1,
                (1, "1"): 1,
                (2, "0"): 2,
                (2, "1"): 2,
            },
        )
        metrics = automaton_metrics(dfa)
        self.assertEqual(metrics.states, 3)
        self.assertEqual(metrics.reachable_states, 2)
        self.assertEqual(metrics.unreachable_states, 1)

    def test_registry_generation_invalidates_planner(self):
        relation = TableRelation("input.one", Operation.INPUT, {"X": (((), __import__('tmam').CostVector(inputs=1), frozenset(), {}),)})
        registry = IntegrationRegistry()
        registry.register_relation(relation)
        planner = TMAMPlanner(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            registry=registry,
            config=PlannerConfig(
                required_relation_ids=frozenset({"input.one"}),
                required_operations=frozenset({Operation.INPUT}),
            ),
        )
        planner.solve_exists(Goal("X", Progress((1,))))
        before = planner.cache_report()["provider"]["size"]
        self.assertGreater(before, 0)
        registry.register_relation(TableRelation("rotate.empty", Operation.ROTATE, {}))
        planner.solve_exists(Goal("X", Progress((1,))))
        self.assertEqual(planner.metrics_snapshot().registry_invalidations, 1)

    def test_selective_family_context_invalidation(self):
        relation = TableRelation("input.one", Operation.INPUT, {"X": (((), __import__('tmam').CostVector(inputs=1), frozenset(), {}),)})
        registry = IntegrationRegistry()
        registry.register_relation(relation)
        planner = TMAMPlanner(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            registry=registry,
            config=PlannerConfig(
                required_relation_ids=frozenset({"input.one"}),
                required_operations=frozenset({Operation.INPUT}),
            ),
        )
        ctx_a = FamilyContext("a")
        ctx_b = FamilyContext("b")
        planner.solve_exists(Goal("X", Progress((1,)), ctx_a))
        planner.solve_exists(Goal("X", Progress((1,)), ctx_b))
        removed = planner.invalidate_family_context(ctx_a)
        self.assertEqual(removed, 1)


if __name__ == "__main__":
    unittest.main()
