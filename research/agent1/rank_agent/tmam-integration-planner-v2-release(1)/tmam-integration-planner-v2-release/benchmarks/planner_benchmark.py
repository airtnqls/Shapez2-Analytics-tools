from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.legacy_planner_reference import (  # noqa: E402
    LegacyTMAMPlanner,
    PlannerConfig as LegacyPlannerConfig,
)
from tmam import (  # noqa: E402
    Certificate,
    CostVector,
    Coverage,
    Goal,
    InverseBatch,
    InverseCandidate,
    IntegrationRegistry,
    Operation,
    PlannerConfig,
    Progress,
    ProofStatus,
    ProofValidator,
    SearchMode,
    Subgoal,
    TMAMPlanner,
    legacy_corner_rule_accepts,
)


class StringBackend:
    def canonicalize(self, shape: str) -> str:
        return shape.strip()

    def key(self, shape: str) -> str:
        return shape.strip()

    def to_code(self, shape: str) -> str:
        return shape.strip()

    def equal(self, left: str, right: str) -> bool:
        return left.strip() == right.strip()

    def is_empty(self, shape: str) -> bool:
        return not shape.strip()

    def has_crystal(self, shape: str) -> bool:
        return "c" in shape

    def active_columns(self, shape: str) -> tuple[int, ...]:
        return (0,) if shape.startswith("CORNER:") else (() if not shape else (0, 1, 2, 3))

    def height(self, shape: str) -> int:
        return 0 if not shape else shape.count(":") + 1


class CertificateForward:
    def replay(self, operation, parents, certificate):
        del operation, parents
        return str(certificate.payload["target"])


@dataclass
class BenchRelation:
    provider_id: str
    operation: Operation
    table: dict[str, list[tuple[tuple[tuple[str, tuple[int, ...], str], ...], int, frozenset[str]]]]
    priority: int = 100
    complete: bool = True
    lower_bound_operations: int = 0
    cache_token: str = "benchmark-v1"
    inverse_calls: int = 0
    candidates_yielded: int = 0
    goals_seen: Counter[str] = None

    def __post_init__(self):
        self.goals_seen = Counter()

    def inverse(self, goal):
        self.inverse_calls += 1
        self.goals_seen[goal.shape] += 1

        def generate():
            for child_specs, cost, traits in self.table.get(goal.shape, []):
                self.candidates_yielded += 1
                yield InverseCandidate(
                    operation=self.operation,
                    target=goal.shape,
                    children=tuple(
                        Subgoal(shape, Progress(progress), role)
                        for shape, progress, role in child_specs
                    ),
                    certificate=Certificate("bench", {"target": goal.shape}),
                    local_cost=CostVector(operations=cost, inputs=int(self.operation is Operation.INPUT)),
                    traits=traits,
                    metadata={"provider": self.provider_id},
                )

        coverage = (
            Coverage.complete_result(token=self.cache_token)
            if self.complete
            else Coverage.partial(reason="benchmark partial", token=self.cache_token)
        )
        return InverseBatch(generate(), coverage)

    def admissible_lower_bound(self, goal):
        del goal
        return CostVector(operations=self.lower_bound_operations)


@dataclass
class CornerRuleRelation:
    provider_id: str = "legacy.corner.rules"
    operation: Operation = Operation.INPUT
    priority: int = 0
    complete: bool = True
    cache_token: str = "corner-six-rules-v1"
    inverse_calls: int = 0
    candidates_yielded: int = 0
    goals_seen: Counter[str] = None

    def __post_init__(self):
        self.goals_seen = Counter()

    def inverse(self, goal):
        self.inverse_calls += 1
        self.goals_seen[goal.shape] += 1
        accepted = legacy_corner_rule_accepts(goal.shape)

        def generate():
            if accepted:
                self.candidates_yielded += 1
                yield InverseCandidate(
                    operation=Operation.INPUT,
                    target=goal.shape,
                    children=(),
                    certificate=Certificate("bench", {"target": goal.shape}),
                    local_cost=CostVector(inputs=1),
                    traits=frozenset({"corner_rule"}),
                )

        return InverseBatch(
            generate(),
            Coverage.complete_result(token=self.cache_token),
            {"real_adapter": "six_corner_forbidden_rules"},
        )


class InstrumentedLegacyPlanner(LegacyTMAMPlanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_hits = 0
        self.cache_misses = 0

    def solve(self, goal):
        canonical = self._canonical_goal(goal)
        key = (self.backend.key(canonical.shape), canonical.progress.components)
        if key in self._memo:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        return super().solve(goal)


@dataclass(frozen=True)
class Scenario:
    name: str
    goal: Goal[str]
    factory: Callable[[], tuple[list[object], frozenset[Operation]]]
    description: str


def graph_relations(kind: str):
    input_table = {
        "A": [((), 0, frozenset({"basic"}))],
        "B": [((), 0, frozenset({"basic"}))],
        "LEAF": [((), 0, frozenset({"basic"}))],
    }
    input_relation = BenchRelation("input.base", Operation.INPUT, input_table, priority=0)
    stack_table = {
        "AB": [((("A", (1,), "bottom"), ("B", (1,), "top")), 1, frozenset({"stack"}))],
    }
    pin_table = {
        "PAB": [((("AB", (2,), "predecessor"),), 1, frozenset({"pp_essential"}))],
    }
    swap_table = {}

    if kind == "shared":
        rows = []
        for i in range(80):
            rows.append(
                (
                    (("LEAF", (1,), "left"), ("LEAF", (1,), "right")),
                    1 if i == 0 else 100 + i,
                    frozenset({"stack", "shared"}),
                )
            )
        stack_table["SHARED_ROOT"] = rows
    elif kind == "multi":
        stack_table["MULTI"] = [
            ((("A", (1,), "bottom"), ("B", (1,), "top")), 2, frozenset({"stack"}))
        ]
        swap_table["MULTI"] = [
            ((("A", (1,), "west"), ("B", (1,), "east")), 1, frozenset({"swap"}))
        ]

    relations = [
        input_relation,
        BenchRelation("stack.graph", Operation.STACK, stack_table, priority=10),
        BenchRelation("pin.graph", Operation.PIN_PUSH, pin_table, priority=20),
        BenchRelation("swap.graph", Operation.SWAP, swap_table, priority=10),
    ]
    required = frozenset({Operation.INPUT, Operation.STACK, Operation.PIN_PUSH, Operation.SWAP})
    return relations, required


def scenarios() -> list[Scenario]:
    return [
        Scenario(
            "possible_goal",
            Goal("PAB", Progress((3,))),
            lambda: graph_relations("possible"),
            "Ranked PinPush -> Stack -> two shared input leaves.",
        ),
        Scenario(
            "impossible_goal",
            Goal("NO", Progress((3,))),
            lambda: graph_relations("impossible"),
            "All complete providers exhaust with no candidate.",
        ),
        Scenario(
            "shared_subgoal_goal",
            Goal("SHARED_ROOT", Progress((2,))),
            lambda: graph_relations("shared"),
            "80 Stack candidates repeatedly reference the same LEAF subgoal.",
        ),
        Scenario(
            "multiple_last_operations_goal",
            Goal("MULTI", Progress((2,))),
            lambda: graph_relations("multi"),
            "Both Stack and Swap have replay-valid proofs.",
        ),
        Scenario(
            "representative_real_corner_provider",
            Goal("S" * 1_000, Progress((1,))),
            lambda: ([CornerRuleRelation()], frozenset({Operation.INPUT})),
            "Actual adapter over the project's six proved corner forbidden rules.",
        ),
    ]


def build_legacy(scenario: Scenario):
    relations, required_operations = scenario.factory()
    registry = IntegrationRegistry()
    for relation in relations:
        registry.register_relation(relation)
    planner = InstrumentedLegacyPlanner(
        backend=StringBackend(),
        registry=registry,
        config=LegacyPlannerConfig(
            required_relation_ids=frozenset(r.provider_id for r in relations),
            required_operations=required_operations,
        ),
    )
    return planner, relations


def build_optimized(scenario: Scenario):
    relations, required_operations = scenario.factory()
    registry = IntegrationRegistry()
    for relation in relations:
        registry.register_relation(relation)
    planner = TMAMPlanner(
        backend=StringBackend(),
        forward=CertificateForward(),
        registry=registry,
        config=PlannerConfig(
            required_relation_ids=frozenset(r.provider_id for r in relations),
            required_operations=required_operations,
        ),
    )
    return planner, relations


def call_mode(planner, implementation: str, mode: str, goal):
    if implementation == "legacy":
        if mode in {"exists", "min_cost"}:
            return planner.solve(goal)
        return planner.analyze(goal)
    if mode == "exists":
        return planner.solve_exists(goal)
    if mode == "min_cost":
        return planner.solve_min_cost(goal)
    return planner.analyze_all_ops(goal)


def extract_semantics(result, mode: str):
    if mode == "all_ops":
        solve = result.solve
        operations = sorted(op.value for op in result.possible_last_operations)
    else:
        solve = result
        operations = None
    return {
        "status": solve.status.value,
        "proof_cost": (
            list(solve.proof.total_cost.__dict__.values()) if solve.proof is not None else None
        ),
        "possible_last_operations": operations,
    }


def relation_metrics(relations):
    inverse_calls = sum(getattr(r, "inverse_calls", 0) for r in relations)
    candidates = sum(getattr(r, "candidates_yielded", 0) for r in relations)
    duplicates = sum(
        max(0, count - 1)
        for relation in relations
        for count in getattr(relation, "goals_seen", {}).values()
    )
    return {
        "provider_inverse_calls": inverse_calls,
        "duplicate_provider_inverse_calls": duplicates,
        "candidate_generated": candidates,
        "per_provider_inverse_calls": {
            r.provider_id: getattr(r, "inverse_calls", 0) for r in relations
        },
    }


def benchmark_one(scenario: Scenario, implementation: str, mode: str, repeats: int):
    builder = build_legacy if implementation == "legacy" else build_optimized
    planner, relations = builder(scenario)
    tracemalloc.start()
    start = time.perf_counter()
    result = None
    for _ in range(repeats):
        result = call_mode(planner, implementation, mode, scenario.goal)
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert result is not None
    semantic = extract_semantics(result, mode)
    relation_data = relation_metrics(relations)
    proof = result.solve.proof if mode == "all_ops" else result.proof
    validation = None
    if proof is not None:
        validation_report = ProofValidator(StringBackend(), CertificateForward()).validate(proof)
        validation = {
            "valid": validation_report.valid,
            "node_count": validation_report.node_count,
            "issues": [issue.code for issue in validation_report.issues],
        }
        if not validation_report.valid:
            raise AssertionError(validation_report.issues)

    if implementation == "optimized":
        metrics = planner.metrics_snapshot().to_dict()
        cache = planner.cache_report()
        provider_requests = metrics["provider_cache_requests"]
        cache_hit_ratio = (
            metrics["provider_cache_hits"] / provider_requests if provider_requests else 0.0
        )
    else:
        metrics = {
            "goal_cache_hits": planner.cache_hits,
            "goal_cache_misses": planner.cache_misses,
            "replay_validations": 0,
        }
        cache = {"legacy_memo_size": len(planner._memo)}
        denom = planner.cache_hits + planner.cache_misses
        cache_hit_ratio = planner.cache_hits / denom if denom else 0.0

    return {
        "scenario": scenario.name,
        "implementation": implementation,
        "mode": mode,
        "repeats": repeats,
        "wall_seconds": elapsed,
        "peak_memory_bytes": peak,
        "cache_hit_ratio": cache_hit_ratio,
        "semantics": semantic,
        "post_run_proof_validation": validation,
        "relations": relation_data,
        "planner_metrics": metrics,
        "cache": cache,
    }


def main():
    output = ROOT / "reports" / "planner_benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    equivalence = []
    for scenario in scenarios():
        for mode in ("exists", "min_cost", "all_ops"):
            for repeats in (1, 10, 100):
                baseline = benchmark_one(scenario, "legacy", mode, repeats)
                optimized = benchmark_one(scenario, "optimized", mode, repeats)
                rows.extend((baseline, optimized))
                same_status = baseline["semantics"]["status"] == optimized["semantics"]["status"]
                same_ops = (
                    mode != "all_ops"
                    or baseline["semantics"]["possible_last_operations"]
                    == optimized["semantics"]["possible_last_operations"]
                )
                same_min_cost = (
                    mode == "exists"
                    or baseline["semantics"]["proof_cost"]
                    == optimized["semantics"]["proof_cost"]
                )
                if not (same_status and same_ops and same_min_cost):
                    raise AssertionError(
                        (scenario.name, mode, repeats, baseline["semantics"], optimized["semantics"])
                    )
                equivalence.append(
                    {
                        "scenario": scenario.name,
                        "mode": mode,
                        "repeats": repeats,
                        "same_status": same_status,
                        "same_possible_last_operations": same_ops,
                        "same_min_cost_when_required": same_min_cost,
                    }
                )

    comparisons = []
    indexed = {
        (row["scenario"], row["mode"], row["repeats"], row["implementation"]): row
        for row in rows
    }
    for scenario in scenarios():
        for mode in ("exists", "min_cost", "all_ops"):
            for repeats in (1, 10, 100):
                before = indexed[(scenario.name, mode, repeats, "legacy")]
                after = indexed[(scenario.name, mode, repeats, "optimized")]
                comparisons.append(
                    {
                        "scenario": scenario.name,
                        "mode": mode,
                        "repeats": repeats,
                        "speedup": (
                            before["wall_seconds"] / after["wall_seconds"]
                            if after["wall_seconds"]
                            else None
                        ),
                        "inverse_call_reduction": (
                            before["relations"]["provider_inverse_calls"]
                            - after["relations"]["provider_inverse_calls"]
                        ),
                        "duplicate_inverse_before": before["relations"]["duplicate_provider_inverse_calls"],
                        "duplicate_inverse_after": after["relations"]["duplicate_provider_inverse_calls"],
                        "peak_memory_ratio_after_over_before": (
                            after["peak_memory_bytes"] / before["peak_memory_bytes"]
                            if before["peak_memory_bytes"]
                            else None
                        ),
                    }
                )

    report = {
        "schema_version": 1,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version,
        "platform": platform.platform(),
        "notes": [
            "Legacy reference is the pre-optimization tmam/planner.py frozen in this release.",
            "The corner scenario is a real adapter over the six proved corner forbidden rules.",
            "Graph scenarios are representative planner workloads, not a claim of full TMAM provider completion.",
            "Wall-time microbenchmarks are environment-dependent; inverse-call and semantic-equivalence counts are the load-bearing results.",
        ],
        "equivalence": equivalence,
        "rows": rows,
        "comparisons": comparisons,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    print(f"rows={len(rows)} comparisons={len(comparisons)}")
    speedups = [row["speedup"] for row in comparisons if row["speedup"] is not None]
    print(f"median_speedup={statistics.median(speedups):.3f}")


if __name__ == "__main__":
    main()
