"""Frozen pre-optimization planner used only for benchmark comparison."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Iterable, Mapping, TypeVar

from tmam.contracts import Goal, InverseCandidate, InverseRelation, ShapeBackend
from tmam.cost import CostModel, LexicographicCostModel
from tmam.enums import Operation, ProofStatus
from tmam.proof import ProofNode
from tmam.registry import IntegrationRegistry

ShapeT = TypeVar("ShapeT")


class PlannerContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannerConfig:
    """Completeness manifest for one solver configuration."""

    required_relation_ids: frozenset[str]
    required_operations: frozenset[Operation] = frozenset(Operation)
    verify_candidate_targets: bool = True


@dataclass(frozen=True)
class SolveResult(Generic[ShapeT]):
    status: ProofStatus
    proof: ProofNode[ShapeT] | None
    complete: bool
    reasons: tuple[str, ...] = ()
    explored_candidates: int = 0


@dataclass(frozen=True)
class OperationEvidence(Generic[ShapeT]):
    operation: Operation
    possible: bool | None
    proof: ProofNode[ShapeT] | None
    complete: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisResult(Generic[ShapeT]):
    solve: SolveResult[ShapeT]
    operations: Mapping[Operation, OperationEvidence[ShapeT]]

    @property
    def possible_last_operations(self) -> frozenset[Operation]:
        return frozenset(op for op, evidence in self.operations.items() if evidence.possible is True)

    @property
    def operation_analysis_complete(self) -> bool:
        return all(evidence.complete for evidence in self.operations.values())


class LegacyTMAMPlanner(Generic[ShapeT]):
    """Memoized AND/OR proof planner over a well-founded progress measure."""

    def __init__(
        self,
        *,
        backend: ShapeBackend[ShapeT],
        registry: IntegrationRegistry[ShapeT],
        config: PlannerConfig,
        cost_model: CostModel | None = None,
    ) -> None:
        self.backend = backend
        self.registry = registry
        self.config = config
        self.cost_model = cost_model or LexicographicCostModel()
        self._memo: dict[tuple[str, tuple[int, ...]], SolveResult[ShapeT]] = {}
        self._active: set[tuple[str, tuple[int, ...]]] = set()

    def clear_cache(self) -> None:
        self._memo.clear()
        self._active.clear()

    def _canonical_goal(self, goal: Goal[ShapeT]) -> Goal[ShapeT]:
        return Goal(self.backend.canonicalize(goal.shape), goal.progress)

    def solve(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        goal = self._canonical_goal(goal)
        key = (self.backend.key(goal.shape), goal.progress.components)
        if key in self._memo:
            return self._memo[key]
        if key in self._active:
            # A conforming provider should never reach this path because every
            # child progress must strictly decrease.
            return SolveResult(
                ProofStatus.INCOMPLETE,
                None,
                False,
                ("cycle detected despite progress contract",),
            )

        self._active.add(key)
        try:
            result = self._solve_uncached(goal)
            self._memo[key] = result
            return result
        finally:
            self._active.remove(key)

    def _solve_uncached(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        missing = self.registry.missing_required_relations(self.config.required_relation_ids)
        missing_operations = frozenset(
            operation
            for operation in self.config.required_operations
            if not self.registry.relations_for(operation)
        )
        complete = not missing and not missing_operations
        reasons: list[str] = [f"missing relation provider: {item}" for item in sorted(missing)]
        reasons.extend(
            f"missing provider for required operation: {operation.value}"
            for operation in sorted(missing_operations, key=lambda item: item.value)
        )
        explored = 0
        best: ProofNode[ShapeT] | None = None

        for relation in self.registry.ordered_relations():
            batch = relation.inverse(goal)
            if not batch.coverage.complete:
                complete = False
                reasons.append(
                    f"{relation.provider_id} partial: {batch.coverage.reason or 'unspecified'}"
                )

            for candidate in batch.candidates:
                explored += 1
                self._validate_candidate_contract(goal, relation, candidate)
                child_results = tuple(
                    self.solve(Goal(child.shape, child.progress)) for child in candidate.children
                )
                if any(child.status is ProofStatus.INCOMPLETE for child in child_results):
                    complete = False
                if not all(child.status is ProofStatus.BUILDABLE for child in child_results):
                    continue

                child_proofs = tuple(child.proof for child in child_results)
                assert all(child is not None for child in child_proofs)
                proofs = tuple(child for child in child_proofs if child is not None)
                total_cost = self.cost_model.combine(
                    candidate.local_cost,
                    tuple(child.total_cost for child in proofs),
                )
                node = ProofNode(
                    shape=goal.shape,
                    shape_key=self.backend.key(goal.shape),
                    shape_code=self.backend.to_code(goal.shape),
                    progress=goal.progress,
                    operation=candidate.operation,
                    children=proofs,
                    certificate=candidate.certificate,
                    local_cost=candidate.local_cost,
                    total_cost=total_cost,
                    traits=candidate.traits,
                    metadata=candidate.metadata,
                )
                if best is None or self.cost_model.ordering_key(total_cost) < self.cost_model.ordering_key(
                    best.total_cost
                ):
                    best = node

        if best is not None:
            return SolveResult(ProofStatus.BUILDABLE, best, complete, tuple(reasons), explored)
        if complete:
            return SolveResult(ProofStatus.IMPOSSIBLE, None, True, tuple(reasons), explored)
        return SolveResult(ProofStatus.INCOMPLETE, None, False, tuple(reasons), explored)

    def _validate_candidate_contract(
        self,
        goal: Goal[ShapeT],
        relation: InverseRelation[ShapeT],
        candidate: InverseCandidate[ShapeT],
    ) -> None:
        if candidate.operation is not relation.operation:
            raise PlannerContractError(
                f"{relation.provider_id}: candidate operation {candidate.operation} != {relation.operation}"
            )
        if self.config.verify_candidate_targets and not self.backend.equal(
            self.backend.canonicalize(candidate.target), goal.shape
        ):
            raise PlannerContractError(f"{relation.provider_id}: candidate target mismatch")
        for child in candidate.children:
            if not goal.progress.allows(child.progress):
                raise PlannerContractError(
                    f"{relation.provider_id}: non-decreasing progress "
                    f"{child.progress.components} from {goal.progress.components}"
                )

    def analyze(self, goal: Goal[ShapeT]) -> AnalysisResult[ShapeT]:
        """Determine buildability and each possible last operation.

        An operation is reported impossible only when every provider for that
        operation is complete and all of its candidates have impossible child
        proofs.  Missing providers produce ``possible=None``.
        """

        goal = self._canonical_goal(goal)
        solve_result = self.solve(goal)
        evidence: dict[Operation, OperationEvidence[ShapeT]] = {}
        for operation in Operation:
            providers = self.registry.relations_for(operation)
            if not providers:
                evidence[operation] = OperationEvidence(
                    operation,
                    None,
                    None,
                    False,
                    ("no provider registered",),
                )
                continue

            operation_complete = True
            operation_reasons: list[str] = []
            best: ProofNode[ShapeT] | None = None
            for relation in providers:
                batch = relation.inverse(goal)
                if not batch.coverage.complete:
                    operation_complete = False
                    operation_reasons.append(
                        f"{relation.provider_id} partial: {batch.coverage.reason or 'unspecified'}"
                    )
                for candidate in batch.candidates:
                    self._validate_candidate_contract(goal, relation, candidate)
                    child_results = tuple(
                        self.solve(Goal(child.shape, child.progress)) for child in candidate.children
                    )
                    if any(child.status is ProofStatus.INCOMPLETE for child in child_results):
                        operation_complete = False
                    if not all(child.status is ProofStatus.BUILDABLE for child in child_results):
                        continue
                    proofs = tuple(child.proof for child in child_results if child.proof is not None)
                    total = self.cost_model.combine(
                        candidate.local_cost,
                        tuple(child.total_cost for child in proofs),
                    )
                    node = ProofNode(
                        shape=goal.shape,
                        shape_key=self.backend.key(goal.shape),
                        shape_code=self.backend.to_code(goal.shape),
                        progress=goal.progress,
                        operation=candidate.operation,
                        children=proofs,
                        certificate=candidate.certificate,
                        local_cost=candidate.local_cost,
                        total_cost=total,
                        traits=candidate.traits,
                        metadata=candidate.metadata,
                    )
                    if best is None or self.cost_model.ordering_key(total) < self.cost_model.ordering_key(
                        best.total_cost
                    ):
                        best = node

            evidence[operation] = OperationEvidence(
                operation,
                True if best is not None else (False if operation_complete else None),
                best,
                operation_complete,
                tuple(operation_reasons),
            )

        return AnalysisResult(solve_result, evidence)
