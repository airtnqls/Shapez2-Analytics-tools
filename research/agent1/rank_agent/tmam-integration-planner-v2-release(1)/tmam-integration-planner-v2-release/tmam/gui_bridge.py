from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .contracts import FamilyContext, Progress
from .enums import LegacyShapeTypeKey, Operation, ProofStatus
from .proof import ProofNode, proof_to_legacy_tree
from .runtime import RuntimeAnalysis, TMAMRuntime

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class PossibilityViewModel(Generic[ShapeT]):
    status: ProofStatus
    proof: ProofNode[ShapeT] | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class MinimumProofViewModel(Generic[ShapeT]):
    status: ProofStatus
    proof: ProofNode[ShapeT] | None
    optimal: bool
    total_cost: object | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DetailedAnalysisViewModel(Generic[ShapeT]):
    status: ProofStatus
    shape_type: LegacyShapeTypeKey
    possible_last_operations: frozenset[Operation]
    proof: ProofNode[ShapeT] | None
    pp_rank: int | None
    stack_depth: int | None
    missing_or_partial_reasons: tuple[str, ...]
    runtime_analysis: RuntimeAnalysis[ShapeT]


class TMAMApplicationService(Generic[ShapeT]):
    """Single GUI entry point; no button re-runs planner/classifier/tracers."""

    def __init__(self, runtime: TMAMRuntime[ShapeT]) -> None:
        self.runtime = runtime

    def check_possible(
        self,
        shape: ShapeT,
        progress: Progress,
        family_context: FamilyContext | None = None,
    ) -> PossibilityViewModel[ShapeT]:
        result = self.runtime.solve_exists(shape, progress, family_context)
        return PossibilityViewModel(result.status, result.proof, result.reasons)

    def minimum_proof(
        self,
        shape: ShapeT,
        progress: Progress,
        family_context: FamilyContext | None = None,
    ) -> MinimumProofViewModel[ShapeT]:
        result = self.runtime.solve_min_cost(shape, progress, family_context)
        return MinimumProofViewModel(
            result.status,
            result.proof,
            result.optimal,
            result.proof.total_cost if result.proof else None,
            result.reasons,
        )

    def detailed_analysis(
        self,
        shape: ShapeT,
        progress: Progress,
        family_context: FamilyContext | None = None,
    ) -> DetailedAnalysisViewModel[ShapeT]:
        result = self.runtime.analyze_all_ops(shape, progress, family_context)
        analysis = result.analysis
        reasons: list[str] = list(analysis.min_cost_result.reasons)
        for evidence in analysis.operations.values():
            reasons.extend(evidence.reasons)
        return DetailedAnalysisViewModel(
            status=analysis.min_cost_result.status,
            shape_type=result.classification.primary,
            possible_last_operations=analysis.possible_last_operations,
            proof=analysis.min_cost_proof,
            pp_rank=result.facts.minimum_pp_rank,
            stack_depth=result.facts.stack_depth,
            missing_or_partial_reasons=tuple(dict.fromkeys(reason for reason in reasons if reason)),
            runtime_analysis=result,
        )

    @staticmethod
    def process_tree_from_proof(proof: ProofNode[ShapeT] | None) -> dict:
        return {} if proof is None else proof_to_legacy_tree(proof)

    def process_tree_from_minimum(self, view: MinimumProofViewModel[ShapeT]) -> dict:
        return self.process_tree_from_proof(view.proof)

    def process_tree_from_analysis(self, view: DetailedAnalysisViewModel[ShapeT]) -> dict:
        return self.process_tree_from_proof(view.proof)
