from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import unittest

from tmam import (
    CallableInverseRelationAdapter,
    Certificate,
    CostVector,
    Coverage,
    FamilyContext,
    Goal,
    InverseBatch,
    InverseCandidate,
    IntegrationRegistry,
    Operation,
    PlannerConfig,
    Progress,
    ProofStatus,
    ProviderResourceLimit,
    Subgoal,
    TMAMApplicationService,
    TMAMPlanner,
    TMAMRuntime,
    legacy_corner_rule_accepts,
    proof_to_precomputed_process_tree,
)

from fakes import CertificateForwardModel, StringBackend


@dataclass
class LazyRelation:
    provider_id: str
    operation: Operation
    rows: dict[str, list[tuple[tuple[tuple[str, tuple[int, ...], str], ...], int]]]
    priority: int = 10
    complete: bool = True
    cache_token: str = "1"
    inverse_calls: int = 0
    yielded: int = 0
    lower_bound_operations: int = 0

    def inverse(self, goal):
        self.inverse_calls += 1

        def generate():
            for child_specs, operations in self.rows.get(goal.shape, []):
                self.yielded += 1
                children = tuple(
                    Subgoal(shape, Progress(progress), role)
                    for shape, progress, role in child_specs
                )
                yield InverseCandidate(
                    operation=self.operation,
                    target=goal.shape,
                    children=children,
                    certificate=Certificate("test", {"target": goal.shape}),
                    local_cost=CostVector(operations=operations),
                    metadata={"provider": self.provider_id},
                )

        coverage = (
            Coverage.complete_result(token=self.cache_token)
            if self.complete
            else Coverage.partial(reason="partial test relation", token=self.cache_token)
        )
        return InverseBatch(generate(), coverage)

    def admissible_lower_bound(self, goal):
        del goal
        return CostVector(operations=self.lower_bound_operations)


class TimeoutRelation(LazyRelation):
    def inverse(self, goal):
        del goal
        self.inverse_calls += 1
        raise TimeoutError("budget reached")


class MismatchForward(CertificateForwardModel):
    def replay(self, operation, parents, certificate):
        del operation, parents, certificate
        return "WRONG"


def make_planner(relations, *, forward=None, required_operations=None):
    registry = IntegrationRegistry()
    for relation in relations:
        registry.register_relation(relation)
    operations = (
        frozenset(required_operations)
        if required_operations is not None
        else frozenset(relation.operation for relation in relations)
    )
    return TMAMPlanner(
        backend=StringBackend(),
        forward=forward or CertificateForwardModel(),
        registry=registry,
        config=PlannerConfig(
            required_relation_ids=frozenset(relation.provider_id for relation in relations),
            required_operations=operations,
        ),
    )


class PlannerModeTests(unittest.TestCase):
    def test_exists_stops_on_first_candidate_and_min_resumes_same_iterator(self):
        relation = LazyRelation(
            "input.lazy",
            Operation.INPUT,
            {"X": [((), cost) for cost in range(1, 51)]},
        )
        planner = make_planner([relation])
        goal = Goal("X", Progress((1,)))

        exists = planner.solve_exists(goal)
        self.assertEqual(exists.status, ProofStatus.POSSIBLE)
        self.assertEqual(relation.inverse_calls, 1)
        self.assertEqual(relation.yielded, 1)
        self.assertEqual(exists.proof.total_cost.operations, 1)

        minimum = planner.solve_min_cost(goal)
        self.assertEqual(minimum.status, ProofStatus.POSSIBLE)
        self.assertTrue(minimum.optimal)
        self.assertEqual(relation.inverse_calls, 1)
        self.assertEqual(relation.yielded, 50)
        self.assertEqual(minimum.proof.total_cost.operations, 1)

        analysis = planner.analyze_all_ops(goal)
        self.assertEqual(analysis.possible_last_operations, frozenset({Operation.INPUT}))
        self.assertEqual(relation.inverse_calls, 1)

    def test_provider_cache_shared_across_modes(self):
        relation = LazyRelation("input.one", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        goal = Goal("X", Progress((1,)))
        planner.solve_exists(goal)
        planner.solve_min_cost(goal)
        planner.analyze_all_ops(goal)
        planner.solve_exists(goal)
        planner.solve_min_cost(goal)
        self.assertEqual(relation.inverse_calls, 1)
        metrics = planner.metrics_snapshot()
        self.assertGreater(metrics.provider_cache_hits, 0)
        self.assertGreater(metrics.duplicate_provider_requests, 0)

    def test_family_context_is_part_of_raw_provider_key(self):
        relation = LazyRelation("input.ctx", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        a = Goal("X", Progress((1,)), FamilyContext("rank", (("n", 1),)))
        b = Goal("X", Progress((1,)), FamilyContext("rank", (("n", 2),)))
        planner.solve_exists(a)
        planner.solve_exists(b)
        self.assertEqual(relation.inverse_calls, 2)

    def test_shared_subgoal_provider_evaluated_once(self):
        leaf = LazyRelation("input.shared", Operation.INPUT, {"S": [((), 0)]}, priority=0)
        stack = LazyRelation(
            "stack.shared",
            Operation.STACK,
            {"ROOT": [((('S', (1,), 'left'), ('S', (1,), 'right')), 1)]},
            priority=10,
        )
        planner = make_planner([leaf, stack], required_operations={Operation.INPUT, Operation.STACK})
        result = planner.solve_min_cost(Goal("ROOT", Progress((2,))))
        self.assertEqual(result.status, ProofStatus.POSSIBLE)
        self.assertEqual(leaf.inverse_calls, 2)  # one for ROOT, one for canonical subgoal S
        # The repeated S child itself shares one S/provider evaluation.
        s_key_calls = planner.metrics_snapshot().subgoal_solve_calls
        self.assertGreaterEqual(s_key_calls.get("min_cost:goal:S@(1,)#default", 0), 2)
        self.assertGreater(planner.metrics_snapshot().goal_cache_hits.get("min_cost", 0), 0)

    def test_negative_result_is_memoized(self):
        relation = LazyRelation("input.empty", Operation.INPUT, {})
        planner = make_planner([relation])
        goal = Goal("NO", Progress((1,)))
        for _ in range(100):
            result = planner.solve_exists(goal)
            self.assertEqual(result.status, ProofStatus.IMPOSSIBLE)
        self.assertEqual(relation.inverse_calls, 1)
        self.assertGreaterEqual(planner.metrics_snapshot().negative_cache_hits, 99)

    def test_partial_and_timeout_never_become_impossible(self):
        partial = LazyRelation("input.partial", Operation.INPUT, {}, complete=False)
        planner = make_planner([partial])
        self.assertEqual(
            planner.solve_exists(Goal("NO", Progress((1,)))).status,
            ProofStatus.UNKNOWN,
        )

        timeout = TimeoutRelation("input.timeout", Operation.INPUT, {})
        planner = make_planner([timeout])
        self.assertEqual(
            planner.solve_min_cost(Goal("NO", Progress((1,)))).status,
            ProofStatus.UNKNOWN,
        )
        self.assertEqual(timeout.inverse_calls, 1)

    def test_forward_replay_is_required_for_possible(self):
        relation = LazyRelation("input.badreplay", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation], forward=MismatchForward())
        result = planner.solve_exists(Goal("X", Progress((1,))))
        self.assertEqual(result.status, ProofStatus.UNKNOWN)
        metrics = planner.metrics_snapshot()
        self.assertEqual(metrics.replay_validations, 1)
        self.assertEqual(metrics.replay_failures, 1)

    def test_branch_and_bound_prunes_expensive_candidate_children(self):
        leaf = LazyRelation(
            "input.leaf",
            Operation.INPUT,
            {"A": [((), 0)], "EXPENSIVE_CHILD": [((), 0)]},
            priority=0,
        )
        relation = LazyRelation(
            "stack.costs",
            Operation.STACK,
            {
                "X": [
                    ((('A', (1,), 'cheap'),), 1),
                    ((('EXPENSIVE_CHILD', (1,), 'expensive'),), 100),
                ]
            },
            priority=10,
        )
        planner = make_planner([leaf, relation], required_operations={Operation.INPUT, Operation.STACK})
        result = planner.solve_min_cost(Goal("X", Progress((2,))))
        self.assertEqual(result.proof.total_cost.operations, 1)
        self.assertGreaterEqual(planner.metrics_snapshot().branch_prunes, 1)
        # EXPENSIVE_CHILD is not recursively solved because its local bound is already worse.
        self.assertFalse(any("EXPENSIVE_CHILD" in key for key in planner.metrics_snapshot().subgoal_solve_calls))

    def test_deterministic_tie_breaker_uses_provider_id(self):
        z = LazyRelation("z.provider", Operation.INPUT, {"X": [((), 1)]}, priority=0)
        a = LazyRelation("a.provider", Operation.INPUT, {"X": [((), 1)]}, priority=0)
        planner = make_planner([z, a])
        result = planner.solve_min_cost(Goal("X", Progress((1,))))
        self.assertEqual(result.proof.metadata["provider"], "a.provider")

    def test_gui_and_process_tree_consume_existing_analysis(self):
        relation = LazyRelation("input.gui", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        runtime = TMAMRuntime(
            backend=StringBackend(),
            forward=CertificateForwardModel(),
            planner=planner,
        )
        service = TMAMApplicationService(runtime)
        fast = service.check_possible("X", Progress((1,)))
        minimum = service.minimum_proof("X", Progress((1,)))
        detailed = service.detailed_analysis("X", Progress((1,)))
        tree = service.process_tree_from_analysis(detailed)
        self.assertEqual(fast.status, ProofStatus.POSSIBLE)
        self.assertEqual(minimum.status, ProofStatus.POSSIBLE)
        self.assertIn("nodes", tree)
        self.assertIn("root_id", tree)
        self.assertEqual(relation.inverse_calls, 1)


    def test_concurrent_same_goal_coalesces_provider_inverse(self):
        relation = LazyRelation("input.concurrent", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        goal = Goal("X", Progress((1,)))

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda _index: planner.solve_exists(goal), range(48)))

        self.assertTrue(all(result.status is ProofStatus.POSSIBLE for result in results))
        self.assertEqual(relation.inverse_calls, 1)
        self.assertEqual(planner.metrics_snapshot().duplicate_provider_inverse_calls, 0)

    def test_precomputed_process_tree_never_invokes_classifier(self):
        relation = LazyRelation("input.tree", Operation.INPUT, {"X": [((), 1)]})
        planner = make_planner([relation])
        proof = planner.solve_min_cost(Goal("X", Progress((1,)))).proof
        self.assertIsNotNone(proof)
        factory_calls = []

        bundle = proof_to_precomputed_process_tree(
            proof,
            shape_factory=lambda code: factory_calls.append(code) or {"code": code},
            root_classification="simple",
            root_reason="precomputed",
        )

        self.assertEqual(relation.inverse_calls, 1)
        self.assertEqual(bundle.root.classification, "simple")
        self.assertEqual(bundle.root.classification_reason, "precomputed")
        self.assertEqual(factory_calls, ["X"])
        self.assertIn(bundle.root.node_id, bundle.nodes_map)

    def test_actual_corner_rule_adapter(self):
        def callback(goal):
            if not legacy_corner_rule_accepts(goal.shape):
                return ()
            return (
                InverseCandidate(
                    operation=Operation.INPUT,
                    target=goal.shape,
                    children=(),
                    certificate=Certificate("test", {"target": goal.shape}),
                    local_cost=CostVector(inputs=1),
                    traits=frozenset({"corner_rule"}),
                ),
            )

        relation = CallableInverseRelationAdapter(
            provider_id="legacy.corner.rules",
            operation=Operation.INPUT,
            callback=callback,
            complete=True,
        )
        planner = make_planner([relation])
        possible = planner.solve_exists(Goal("SSScS", Progress((1,))))
        impossible = planner.solve_exists(Goal("-P", Progress((1,))))
        self.assertEqual(possible.status, ProofStatus.POSSIBLE)
        self.assertEqual(impossible.status, ProofStatus.IMPOSSIBLE)


if __name__ == "__main__":
    unittest.main()
