from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Generic, TypeVar

from .classification import ClassificationPolicy, ClassificationResult
from .contracts import ForwardModel, Goal, Progress, ShapeBackend
from .facts import ShapeFacts, facts_from_analysis
from .planner import GoalAnalysis, SolveResult, TMAMPlanner
from .proof import ProofValidator, ValidationReport

ShapeT = TypeVar("ShapeT")


@dataclass(frozen=True)
class RuntimeAnalysis(Generic[ShapeT]):
    analysis: GoalAnalysis[ShapeT]
    facts: ShapeFacts[ShapeT]
    classification: ClassificationResult
    proof_validation: ValidationReport | None


class TMAMRuntime(Generic[ShapeT]):
    def __init__(
        self,
        *,
        backend: ShapeBackend[ShapeT],
        forward: ForwardModel[ShapeT],
        planner: TMAMPlanner[ShapeT],
        classification: ClassificationPolicy | None = None,
    ) -> None:
        self.backend = backend
        self.forward = forward
        self.planner = planner
        self.classification = classification or ClassificationPolicy()
        self.validator = ProofValidator(backend, forward)
        if planner.forward is None:
            planner.forward = forward
        self._analysis_cache: dict[tuple[str, tuple[int, ...], object, int, int], RuntimeAnalysis[ShapeT]] = {}
        self._validation_cache: dict[str, ValidationReport] = {}

    def solve_exists(self, shape: ShapeT, progress: Progress, family_context=None) -> SolveResult[ShapeT]:
        goal = Goal(shape, progress) if family_context is None else Goal(shape, progress, family_context)
        return self.planner.solve_exists(goal)

    def solve_min_cost(self, shape: ShapeT, progress: Progress, family_context=None) -> SolveResult[ShapeT]:
        goal = Goal(shape, progress) if family_context is None else Goal(shape, progress, family_context)
        return self.planner.solve_min_cost(goal)

    def analyze_all_ops(
        self,
        shape: ShapeT,
        progress: Progress,
        family_context=None,
        *,
        validate_proof: bool = False,
    ) -> RuntimeAnalysis[ShapeT]:
        goal = Goal(shape, progress) if family_context is None else Goal(shape, progress, family_context)
        self.planner.ensure_fresh()
        canonical = self.backend.canonicalize(shape)
        key = (
            self.backend.key(canonical),
            progress.components,
            goal.family_context.cache_key,
            self.planner.registry.generation,
            self.planner.cache_epoch,
        )
        cached = self._analysis_cache.get(key)
        if cached is None:
            analysis = self.planner.analyze_all_ops(goal)
            facts = facts_from_analysis(self.backend, canonical, analysis)
            analysis = replace(analysis, classification_facts=facts)
            classification = self.classification.classify(facts)
            cached = RuntimeAnalysis(analysis, facts, classification, None)
            self._analysis_cache[key] = cached

        if not validate_proof or cached.analysis.min_cost_proof is None:
            return cached
        proof = cached.analysis.min_cost_proof
        digest = proof.stable_digest()
        validation = self._validation_cache.get(digest)
        if validation is None:
            validation = self.validator.validate(proof)
            self._validation_cache[digest] = validation
        return replace(cached, proof_validation=validation)

    def validate_proof(self, proof) -> ValidationReport:
        digest = proof.stable_digest()
        cached = self._validation_cache.get(digest)
        if cached is None:
            cached = self.validator.validate(proof)
            self._validation_cache[digest] = cached
        return cached

    def analyze(self, shape: ShapeT, progress: Progress) -> RuntimeAnalysis[ShapeT]:
        """Compatibility alias preserving the old full-proof validation."""

        return self.analyze_all_ops(shape, progress, validate_proof=True)

    def clear_cache(self) -> None:
        self.planner.clear_cache()
        self._analysis_cache.clear()
        self._validation_cache.clear()
