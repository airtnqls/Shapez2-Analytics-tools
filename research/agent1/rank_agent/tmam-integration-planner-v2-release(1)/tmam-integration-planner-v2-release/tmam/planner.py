from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import RLock, local
from typing import Any, Generic, Iterable, Mapping, TypeVar

from .cache import CandidateCacheKey, GenerationalCache, GoalCacheKey, ProviderCacheKey
from .contracts import (
    Coverage,
    FamilyContext,
    ForwardModel,
    Goal,
    InverseBatch,
    InverseCandidate,
    InverseRelation,
    ProviderIncompleteError,
    ProviderResourceLimit,
    ShapeBackend,
)
from .cost import CostModel, CostVector, LexicographicCostModel
from .enums import Operation, ProofStatus, SearchMode
from .instrumentation import PlannerInstrumentation, PlannerMetricsSnapshot
from .proof import ProofNode
from .registry import IntegrationRegistry

ShapeT = TypeVar("ShapeT")


class PlannerContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlannerConfig:
    """Completeness and execution policy for one planner instance."""

    required_relation_ids: frozenset[str]
    required_operations: frozenset[Operation] = frozenset(Operation)
    verify_candidate_targets: bool = True
    require_forward_replay: bool = True
    provider_errors_as_unknown: bool = True
    enable_branch_and_bound: bool = True
    trace_limit: int = 20_000


@dataclass(frozen=True)
class SolveResult(Generic[ShapeT]):
    status: ProofStatus
    proof: ProofNode[ShapeT] | None
    complete: bool
    reasons: tuple[str, ...] = ()
    explored_candidates: int = 0
    mode: SearchMode = SearchMode.MIN_COST
    optimal: bool = False
    search_exhausted: bool = False

    @property
    def possible(self) -> bool:
        return self.status is ProofStatus.POSSIBLE


@dataclass(frozen=True)
class ProviderEvaluation(Generic[ShapeT]):
    provider_id: str
    operation: Operation
    candidates: tuple[InverseCandidate[ShapeT], ...]
    complete: bool
    exhausted: bool
    diagnostics: Mapping[str, Any]
    coverage: Coverage


@dataclass(frozen=True)
class OperationEvidence(Generic[ShapeT]):
    operation: Operation
    possible: bool | None
    proof: ProofNode[ShapeT] | None
    complete: bool
    reasons: tuple[str, ...] = ()
    provider_results: Mapping[str, ProviderEvaluation[ShapeT]] = field(default_factory=dict)
    explored_candidates: int = 0
    optimal: bool = False


@dataclass(frozen=True)
class GoalAnalysis(Generic[ShapeT]):
    goal: Goal[ShapeT]
    exists_result: SolveResult[ShapeT]
    min_cost_result: SolveResult[ShapeT]
    operations: Mapping[Operation, OperationEvidence[ShapeT]]
    provider_results: Mapping[str, ProviderEvaluation[ShapeT]]
    classification_facts: object | None = None

    @property
    def exists_proof(self) -> ProofNode[ShapeT] | None:
        return self.exists_result.proof

    @property
    def min_cost_proof(self) -> ProofNode[ShapeT] | None:
        return self.min_cost_result.proof

    @property
    def possible_last_operations(self) -> frozenset[Operation]:
        return frozenset(op for op, evidence in self.operations.items() if evidence.possible is True)

    @property
    def operation_analysis_complete(self) -> bool:
        return all(evidence.complete for evidence in self.operations.values())

    # Compatibility with the first integration prototype.
    @property
    def solve(self) -> SolveResult[ShapeT]:
        return self.min_cost_result


AnalysisResult = GoalAnalysis


@dataclass(frozen=True)
class _CandidateOutcome(Generic[ShapeT]):
    status: ProofStatus
    proof: ProofNode[ShapeT] | None
    reasons: tuple[str, ...] = ()
    optimal: bool = False


@dataclass
class _ProviderEvaluationState(Generic[ShapeT]):
    relation: InverseRelation[ShapeT]
    goal: Goal[ShapeT]
    key: ProviderCacheKey
    started: bool = False
    iterator: Any = None
    candidates: list[InverseCandidate[ShapeT]] = field(default_factory=list)
    coverage: Coverage = field(default_factory=lambda: Coverage.partial(reason="not evaluated"))
    exhausted: bool = False
    trusted: bool = True
    diagnostics: dict[str, Any] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock, repr=False)

    @property
    def complete(self) -> bool:
        return self.coverage.complete and self.trusted

    def snapshot(self) -> ProviderEvaluation[ShapeT]:
        return ProviderEvaluation(
            provider_id=self.relation.provider_id,
            operation=self.relation.operation,
            candidates=tuple(self.candidates),
            complete=self.complete,
            exhausted=self.exhausted,
            diagnostics=dict(self.diagnostics),
            coverage=self.coverage,
        )


@dataclass(frozen=True)
class _BestChoice(Generic[ShapeT]):
    proof: ProofNode[ShapeT]
    provider_id: str
    ordinal: int


class TMAMPlanner(Generic[ShapeT]):
    """Shared-evaluation AND/OR planner with three purpose-specific modes.

    Raw provider iterators are invoked once per canonical goal/provider/family
    context.  EXISTS may stop after the first replay-verified proof; MIN_COST
    resumes the same iterators and exhausts only what is necessary; ALL_OPS
    consumes the same cached graph and never re-runs inverse providers.
    """

    def __init__(
        self,
        *,
        backend: ShapeBackend[ShapeT],
        registry: IntegrationRegistry[ShapeT],
        config: PlannerConfig,
        forward: ForwardModel[ShapeT] | None = None,
        cost_model: CostModel | None = None,
    ) -> None:
        self.backend = backend
        self.registry = registry
        self.config = config
        self.forward = forward
        self.cost_model = cost_model or LexicographicCostModel()
        self.instrumentation = PlannerInstrumentation(trace_limit=config.trace_limit)

        self._provider_states: GenerationalCache[ProviderCacheKey, _ProviderEvaluationState[ShapeT]] = GenerationalCache()
        self._exists_cache: dict[GoalCacheKey, SolveResult[ShapeT]] = {}
        self._min_cache: dict[GoalCacheKey, SolveResult[ShapeT]] = {}
        self._operation_cache: dict[tuple[GoalCacheKey, Operation], OperationEvidence[ShapeT]] = {}
        self._analysis_cache: dict[GoalCacheKey, GoalAnalysis[ShapeT]] = {}
        self._candidate_exists_cache: dict[CandidateCacheKey, _CandidateOutcome[ShapeT]] = {}
        self._candidate_min_cache: dict[CandidateCacheKey, _CandidateOutcome[ShapeT]] = {}
        self._candidate_contract_validated: set[CandidateCacheKey] = set()
        self._replay_cache: dict[CandidateCacheKey, tuple[bool | None, str]] = {}
        self._thread_state = local()
        self._registry_generation = registry.generation
        self._cache_epoch = 0
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Cache and instrumentation API
    # ------------------------------------------------------------------
    @property
    def cache_epoch(self) -> int:
        """Monotone token changed by every explicit or registry invalidation."""

        return self._cache_epoch

    def clear_cache(self) -> None:
        with self._lock:
            self._provider_states.invalidate()
            self._clear_derived_caches()
            self._cache_epoch += 1

    def _clear_derived_caches(self) -> None:
        self._exists_cache.clear()
        self._min_cache.clear()
        self._operation_cache.clear()
        self._analysis_cache.clear()
        self._candidate_exists_cache.clear()
        self._candidate_min_cache.clear()
        self._candidate_contract_validated.clear()
        self._replay_cache.clear()

    def invalidate_provider(self, provider_id: str | None = None) -> int:
        """Invalidate raw evaluations and every proof depending on them."""

        with self._lock:
            if provider_id is None:
                count = self._provider_states.invalidate()
            else:
                count = self._provider_states.invalidate(
                    lambda key, _value: key.provider_id == provider_id
                )
            self._clear_derived_caches()
            self._cache_epoch += 1
            return count

    def invalidate_family_context(self, family_context: FamilyContext) -> int:
        with self._lock:
            context_key = family_context.cache_key
            count = self._provider_states.invalidate(
                lambda key, _value: key.goal.family_context == context_key
            )
            self._clear_derived_caches()
            self._cache_epoch += 1
            return count

    def reset_metrics(self) -> None:
        self.instrumentation.reset()

    def metrics_snapshot(self) -> PlannerMetricsSnapshot:
        return self.instrumentation.snapshot()

    def call_graph_dot(self) -> str:
        return self.instrumentation.call_graph_dot()

    def cache_report(self) -> dict[str, Any]:
        return {
            "provider": self._provider_states.stats().__dict__,
            "exists_goals": len(self._exists_cache),
            "min_cost_goals": len(self._min_cache),
            "operation_evidence": len(self._operation_cache),
            "goal_analyses": len(self._analysis_cache),
            "candidate_exists": len(self._candidate_exists_cache),
            "candidate_min_cost": len(self._candidate_min_cache),
            "replay_checks": len(self._replay_cache),
            "registry_generation": self._registry_generation,
            "cache_epoch": self._cache_epoch,
        }

    def ensure_fresh(self) -> None:
        """Synchronize registry generation before a caller builds external cache keys."""

        self._sync_registry_generation()

    def _sync_registry_generation(self) -> None:
        if self.registry.generation == self._registry_generation:
            return
        with self._lock:
            if self.registry.generation != self._registry_generation:
                self.clear_cache()
                self._registry_generation = self.registry.generation
                self.instrumentation.registry_invalidations += 1

    # ------------------------------------------------------------------
    # Goal/provider identity
    # ------------------------------------------------------------------
    def _canonical_goal(self, goal: Goal[ShapeT]) -> Goal[ShapeT]:
        return Goal(
            self.backend.canonicalize(goal.shape),
            goal.progress,
            goal.family_context,
        )

    def _goal_key(self, goal: Goal[ShapeT]) -> GoalCacheKey:
        return GoalCacheKey.build(
            self.backend.key(goal.shape),
            goal.progress,
            goal.family_context,
            self._registry_generation,
        )

    @staticmethod
    def _provider_revision(relation: InverseRelation[ShapeT]) -> str:
        return str(
            getattr(
                relation,
                "cache_token",
                getattr(relation, "version", "0"),
            )
        )

    def _provider_state(
        self,
        goal: Goal[ShapeT],
        relation: InverseRelation[ShapeT],
    ) -> _ProviderEvaluationState[ShapeT]:
        goal_key = self._goal_key(goal)
        key = ProviderCacheKey(goal_key, relation.provider_id, self._provider_revision(relation))
        self.instrumentation.provider_cache_requests += 1
        state, hit = self._provider_states.get_or_create(
            key,
            lambda: _ProviderEvaluationState(relation=relation, goal=goal, key=key),
        )
        if hit:
            self.instrumentation.provider_cache_hits += 1
            self.instrumentation.duplicate_provider_requests += 1
        else:
            self.instrumentation.provider_cache_misses += 1
        return state

    def _start_provider(self, state: _ProviderEvaluationState[ShapeT]) -> None:
        with state.lock:
            if state.started:
                return
            state.started = True
            relation = state.relation
            self.instrumentation.provider_inverse_calls[relation.provider_id] += 1
            self.instrumentation.provider_inverse_key_calls[repr(state.key)] += 1
            self.instrumentation.trace(
                "inverse",
                self._goal_label(state.goal),
                f"provider:{relation.provider_id}",
                relation.operation.value,
            )
            try:
                batch = relation.inverse(state.goal)
                if not isinstance(batch, InverseBatch):
                    raise TypeError(
                        f"{relation.provider_id}.inverse() returned {type(batch).__name__}, expected InverseBatch"
                    )
                state.coverage = batch.coverage
                state.iterator = iter(batch.candidates)
                state.diagnostics.update(dict(batch.diagnostics))
                if not batch.coverage.complete:
                    self.instrumentation.provider_incomplete_events += 1
            except (ProviderResourceLimit, ProviderIncompleteError, TimeoutError, NotImplementedError) as exc:
                state.coverage = Coverage.partial(reason=str(exc) or exc.__class__.__name__)
                state.exhausted = True
                state.trusted = False
                state.diagnostics["incomplete_error"] = f"{exc.__class__.__name__}: {exc}"
                self.instrumentation.provider_incomplete_events += 1
            except Exception as exc:
                if not self.config.provider_errors_as_unknown:
                    raise
                state.coverage = Coverage.partial(reason=f"provider error: {exc}")
                state.exhausted = True
                state.trusted = False
                state.diagnostics["provider_error"] = f"{exc.__class__.__name__}: {exc}"
                self.instrumentation.provider_incomplete_events += 1

    def _candidate_at(
        self,
        state: _ProviderEvaluationState[ShapeT],
        ordinal: int,
    ) -> InverseCandidate[ShapeT] | None:
        self._start_provider(state)
        with state.lock:
            if ordinal < len(state.candidates):
                self.instrumentation.candidate_cache_hits[state.relation.provider_id] += 1
                return state.candidates[ordinal]
            if state.exhausted:
                return None
            try:
                candidate = next(state.iterator)
            except StopIteration:
                state.exhausted = True
                return None
            except (ProviderResourceLimit, ProviderIncompleteError, TimeoutError, NotImplementedError) as exc:
                state.coverage = Coverage.partial(reason=str(exc) or exc.__class__.__name__)
                state.exhausted = True
                state.trusted = False
                state.diagnostics["generation_incomplete"] = f"{exc.__class__.__name__}: {exc}"
                self.instrumentation.provider_incomplete_events += 1
                return None
            except Exception as exc:
                if not self.config.provider_errors_as_unknown:
                    raise
                state.coverage = Coverage.partial(reason=f"candidate generation error: {exc}")
                state.exhausted = True
                state.trusted = False
                state.diagnostics["generation_error"] = f"{exc.__class__.__name__}: {exc}"
                self.instrumentation.provider_incomplete_events += 1
                return None

            state.candidates.append(candidate)
            self.instrumentation.candidate_generated[state.relation.provider_id] += 1
            self.instrumentation.trace(
                "candidate",
                f"provider:{state.relation.provider_id}",
                f"candidate:{state.relation.provider_id}:{ordinal}",
                candidate.operation.value,
            )
            return candidate

    def provider_evaluation(
        self,
        goal: Goal[ShapeT],
        provider_id: str,
        *,
        exhaust: bool = False,
    ) -> ProviderEvaluation[ShapeT]:
        self._sync_registry_generation()
        goal = self._canonical_goal(goal)
        relation = self.registry.relations[provider_id]
        state = self._provider_state(goal, relation)
        self._start_provider(state)
        if exhaust:
            ordinal = len(state.candidates)
            while self._candidate_at(state, ordinal) is not None:
                ordinal += 1
        return state.snapshot()

    def _active_set(self, mode: SearchMode) -> set[GoalCacheKey]:
        name = f"active_{mode.value}"
        active = getattr(self._thread_state, name, None)
        if active is None:
            active = set()
            setattr(self._thread_state, name, active)
        return active

    # ------------------------------------------------------------------
    # Public search modes
    # ------------------------------------------------------------------
    def solve_exists(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        self._sync_registry_generation()
        goal = self._canonical_goal(goal)
        key = self._goal_key(goal)
        self.instrumentation.record_goal_call(SearchMode.EXISTS, self._goal_label(goal), len(self._active_set(SearchMode.EXISTS)))

        min_cached = self._min_cache.get(key)
        if min_cached is not None:
            self.instrumentation.goal_cache_hits[SearchMode.EXISTS.value] += 1
            return replace(min_cached, mode=SearchMode.EXISTS, optimal=False)
        cached = self._exists_cache.get(key)
        if cached is not None:
            self.instrumentation.goal_cache_hits[SearchMode.EXISTS.value] += 1
            if cached.status is ProofStatus.IMPOSSIBLE:
                self.instrumentation.negative_cache_hits += 1
            return cached
        self.instrumentation.goal_cache_misses[SearchMode.EXISTS.value] += 1

        active = self._active_set(SearchMode.EXISTS)
        if key in active:
            self.instrumentation.cycle_blocks += 1
            return SolveResult(
                ProofStatus.UNKNOWN,
                None,
                False,
                ("recursion-stack cycle",),
                mode=SearchMode.EXISTS,
            )

        active.add(key)
        try:
            result = self._solve_exists_uncached(goal)
            self._exists_cache[key] = result
            return result
        finally:
            active.remove(key)

    def solve_min_cost(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        self._sync_registry_generation()
        goal = self._canonical_goal(goal)
        key = self._goal_key(goal)
        self.instrumentation.record_goal_call(SearchMode.MIN_COST, self._goal_label(goal), len(self._active_set(SearchMode.MIN_COST)))

        cached = self._min_cache.get(key)
        if cached is not None:
            self.instrumentation.goal_cache_hits[SearchMode.MIN_COST.value] += 1
            if cached.status is ProofStatus.IMPOSSIBLE:
                self.instrumentation.negative_cache_hits += 1
            return cached
        self.instrumentation.goal_cache_misses[SearchMode.MIN_COST.value] += 1

        exists_cached = self._exists_cache.get(key)
        if exists_cached is not None and exists_cached.status is not ProofStatus.POSSIBLE:
            inherited = replace(exists_cached, mode=SearchMode.MIN_COST, optimal=False)
            self._min_cache[key] = inherited
            return inherited

        active = self._active_set(SearchMode.MIN_COST)
        if key in active:
            self.instrumentation.cycle_blocks += 1
            return SolveResult(
                ProofStatus.UNKNOWN,
                None,
                False,
                ("recursion-stack cycle",),
                mode=SearchMode.MIN_COST,
            )

        active.add(key)
        try:
            result = self._solve_min_cost_uncached(goal)
            self._min_cache[key] = result
            if key not in self._exists_cache:
                self._exists_cache[key] = replace(result, mode=SearchMode.EXISTS, optimal=False)
            return result
        finally:
            active.remove(key)

    def analyze_all_ops(self, goal: Goal[ShapeT]) -> GoalAnalysis[ShapeT]:
        self._sync_registry_generation()
        goal = self._canonical_goal(goal)
        key = self._goal_key(goal)
        cached = self._analysis_cache.get(key)
        if cached is not None:
            self.instrumentation.goal_cache_hits[SearchMode.ALL_OPS.value] += 1
            return cached
        self.instrumentation.goal_cache_misses[SearchMode.ALL_OPS.value] += 1

        min_result = self.solve_min_cost(goal)
        exists_result = self._exists_cache.get(key) or replace(
            min_result,
            mode=SearchMode.EXISTS,
            optimal=False,
        )
        operations = {
            operation: self._operation_evidence(goal, operation)
            for operation in Operation
        }
        provider_results: dict[str, ProviderEvaluation[ShapeT]] = {}
        for relation in self.registry.ordered_relations():
            state = self._provider_state(goal, relation)
            provider_results[relation.provider_id] = state.snapshot()

        analysis = GoalAnalysis(
            goal=goal,
            exists_result=exists_result,
            min_cost_result=min_result,
            operations=operations,
            provider_results=provider_results,
        )
        self._analysis_cache[key] = analysis
        return analysis

    # Compatibility aliases -------------------------------------------------
    def solve(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        """Compatibility alias: the old solve() meant minimum-cost solve."""

        return self.solve_min_cost(goal)

    def analyze(self, goal: Goal[ShapeT]) -> GoalAnalysis[ShapeT]:
        return self.analyze_all_ops(goal)

    # ------------------------------------------------------------------
    # EXISTS implementation
    # ------------------------------------------------------------------
    def _solve_exists_uncached(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        missing_reasons = self._missing_configuration_reasons()
        unknown = bool(missing_reasons)
        reasons = list(missing_reasons)
        explored = 0
        all_exhausted = True

        for relation in self.registry.ordered_relations():
            state = self._provider_state(goal, relation)
            ordinal = 0
            while True:
                candidate = self._candidate_at(state, ordinal)
                if candidate is None:
                    break
                explored += 1
                outcome = self._evaluate_candidate_exists(goal, state, ordinal, candidate)
                if outcome.status is ProofStatus.POSSIBLE:
                    return SolveResult(
                        ProofStatus.POSSIBLE,
                        outcome.proof,
                        True,
                        tuple(reasons),
                        explored,
                        SearchMode.EXISTS,
                        optimal=False,
                        search_exhausted=False,
                    )
                if outcome.status is ProofStatus.UNKNOWN:
                    unknown = True
                    reasons.extend(outcome.reasons)
                ordinal += 1

            if not state.complete:
                unknown = True
                reasons.append(self._provider_incomplete_reason(state))
            all_exhausted = all_exhausted and state.exhausted

        if not unknown and all_exhausted:
            return SolveResult(
                ProofStatus.IMPOSSIBLE,
                None,
                True,
                tuple(_dedupe(reasons)),
                explored,
                SearchMode.EXISTS,
                optimal=False,
                search_exhausted=True,
            )
        return SolveResult(
            ProofStatus.UNKNOWN,
            None,
            False,
            tuple(_dedupe(reasons)),
            explored,
            SearchMode.EXISTS,
            optimal=False,
            search_exhausted=all_exhausted,
        )

    def _evaluate_candidate_exists(
        self,
        goal: Goal[ShapeT],
        state: _ProviderEvaluationState[ShapeT],
        ordinal: int,
        candidate: InverseCandidate[ShapeT],
    ) -> _CandidateOutcome[ShapeT]:
        key = CandidateCacheKey(state.key, ordinal)
        cached = self._candidate_exists_cache.get(key)
        if cached is not None:
            self.instrumentation.candidate_cache_hits[f"exists:{state.relation.provider_id}"] += 1
            return cached
        self._validate_candidate_contract(goal, state, key, candidate)

        child_proofs: list[ProofNode[ShapeT]] = []
        unknown_reasons: list[str] = []
        for child in candidate.children:
            child_goal = self._child_goal(goal, child)
            self.instrumentation.trace(
                "subgoal",
                self._goal_label(goal),
                self._goal_label(child_goal),
                child.role,
            )
            result = self.solve_exists(child_goal)
            if result.status is ProofStatus.IMPOSSIBLE:
                outcome = _CandidateOutcome(ProofStatus.IMPOSSIBLE, None)
                self._candidate_exists_cache[key] = outcome
                return outcome
            if result.status is ProofStatus.UNKNOWN:
                unknown_reasons.extend(result.reasons or (f"unknown child: {child.role}",))
            elif result.proof is not None:
                child_proofs.append(result.proof)

        if unknown_reasons:
            outcome = _CandidateOutcome(
                ProofStatus.UNKNOWN,
                None,
                tuple(_dedupe(unknown_reasons)),
            )
            self._candidate_exists_cache[key] = outcome
            return outcome

        replay_ok, replay_reason = self._verify_candidate_replay(goal, state, key, candidate)
        if replay_ok is not True:
            outcome = _CandidateOutcome(
                ProofStatus.UNKNOWN,
                None,
                (replay_reason or "forward replay unavailable",),
            )
            self._candidate_exists_cache[key] = outcome
            return outcome

        proofs = tuple(child_proofs)
        total_cost = self.cost_model.combine(
            candidate.local_cost,
            tuple(child.total_cost for child in proofs),
        )
        node = self._build_proof(goal, candidate, proofs, total_cost)
        outcome = _CandidateOutcome(ProofStatus.POSSIBLE, node, optimal=False)
        self._candidate_exists_cache[key] = outcome
        return outcome

    # ------------------------------------------------------------------
    # MIN_COST / operation analysis implementation
    # ------------------------------------------------------------------
    def _solve_min_cost_uncached(self, goal: Goal[ShapeT]) -> SolveResult[ShapeT]:
        evidences = [self._operation_evidence(goal, operation) for operation in Operation]
        best: _BestChoice[ShapeT] | None = None
        explored = 0
        optimal = True
        reasons: list[str] = list(self._missing_configuration_reasons())
        if reasons:
            optimal = False

        for evidence in evidences:
            explored += evidence.explored_candidates
            if evidence.proof is not None:
                choice = _BestChoice(evidence.proof, f"operation:{evidence.operation.value}", 0)
                best = self._choose_better(best, choice)
            if not evidence.complete or not evidence.optimal:
                optimal = False
            reasons.extend(evidence.reasons)

        if best is not None:
            return SolveResult(
                ProofStatus.POSSIBLE,
                best.proof,
                True,
                tuple(_dedupe(reasons)),
                explored,
                SearchMode.MIN_COST,
                optimal=optimal,
                search_exhausted=all(evidence.complete for evidence in evidences),
            )

        if all(evidence.possible is False and evidence.complete for evidence in evidences) and not self._missing_configuration_reasons():
            return SolveResult(
                ProofStatus.IMPOSSIBLE,
                None,
                True,
                tuple(_dedupe(reasons)),
                explored,
                SearchMode.MIN_COST,
                optimal=True,
                search_exhausted=True,
            )

        return SolveResult(
            ProofStatus.UNKNOWN,
            None,
            False,
            tuple(_dedupe(reasons)),
            explored,
            SearchMode.MIN_COST,
            optimal=False,
            search_exhausted=False,
        )

    def _operation_evidence(
        self,
        goal: Goal[ShapeT],
        operation: Operation,
    ) -> OperationEvidence[ShapeT]:
        goal_key = self._goal_key(goal)
        cache_key = (goal_key, operation)
        cached = self._operation_cache.get(cache_key)
        if cached is not None:
            self.instrumentation.goal_cache_hits[f"operation:{operation.value}"] += 1
            return cached
        self.instrumentation.goal_cache_misses[f"operation:{operation.value}"] += 1

        providers = self.registry.relations_for(operation)
        if not providers:
            required = operation in self.config.required_operations
            evidence = OperationEvidence(
                operation=operation,
                possible=None if required else False,
                proof=None,
                complete=not required,
                reasons=(("no provider registered",) if required else ("operation disabled by planner configuration",)),
                optimal=not required,
            )
            self._operation_cache[cache_key] = evidence
            return evidence

        provider_rows: list[tuple[tuple[int, ...], InverseRelation[ShapeT]]] = []
        for relation in providers:
            lower = self._provider_lower_bound(relation, goal)
            provider_rows.append((self.cost_model.ordering_key(lower), relation))
        provider_rows.sort(key=lambda row: (row[0], row[1].priority, row[1].provider_id))

        best: _BestChoice[ShapeT] | None = None
        unknown = False
        reasons: list[str] = []
        explored = 0
        provider_results: dict[str, ProviderEvaluation[ShapeT]] = {}
        safely_pruned_providers: set[str] = set()

        for provider_lower_key, relation in provider_rows:
            if (
                self.config.enable_branch_and_bound
                and best is not None
                and provider_lower_key > self.cost_model.ordering_key(best.proof.total_cost)
            ):
                self.instrumentation.branch_prunes += 1
                safely_pruned_providers.add(relation.provider_id)
                state = self._provider_state(goal, relation)
                state.diagnostics["pruned_by_admissible_lower_bound"] = {
                    "provider_lower_bound": list(provider_lower_key),
                    "current_best": list(self.cost_model.ordering_key(best.proof.total_cost)),
                }
                provider_results[relation.provider_id] = state.snapshot()
                continue

            state = self._provider_state(goal, relation)
            ordinal = 0
            while True:
                candidate = self._candidate_at(state, ordinal)
                if candidate is None:
                    break
                explored += 1
                if (
                    self.config.enable_branch_and_bound
                    and best is not None
                    and self.cost_model.ordering_key(candidate.local_cost)
                    > self.cost_model.ordering_key(best.proof.total_cost)
                ):
                    self.instrumentation.branch_prunes += 1
                    ordinal += 1
                    continue

                outcome = self._evaluate_candidate_min(goal, state, ordinal, candidate)
                if outcome.status is ProofStatus.POSSIBLE and outcome.proof is not None:
                    best = self._choose_better(
                        best,
                        _BestChoice(outcome.proof, relation.provider_id, ordinal),
                    )
                    if not outcome.optimal:
                        unknown = True
                elif outcome.status is ProofStatus.UNKNOWN:
                    unknown = True
                    reasons.extend(outcome.reasons)
                ordinal += 1

            if not state.complete:
                unknown = True
                reasons.append(self._provider_incomplete_reason(state))
            provider_results[relation.provider_id] = state.snapshot()

        physically_or_safely_exhausted = all(
            result.exhausted or provider_id in safely_pruned_providers
            for provider_id, result in provider_results.items()
        )
        negative_complete = (
            all(result.complete and result.exhausted for result in provider_results.values())
            and not unknown
        )
        cost_resolved = physically_or_safely_exhausted and not unknown and all(
            result.complete or provider_id in safely_pruned_providers
            for provider_id, result in provider_results.items()
        )

        if best is not None:
            # A replayed witness makes operation existence definitive even if a
            # different partial provider remains.  Only cost optimality depends
            # on exhausting or safely lower-bound-pruning every competitor.
            evidence = OperationEvidence(
                operation=operation,
                possible=True,
                proof=best.proof,
                complete=True,
                reasons=tuple(_dedupe(reasons)),
                provider_results=provider_results,
                explored_candidates=explored,
                optimal=cost_resolved,
            )
        elif negative_complete:
            evidence = OperationEvidence(
                operation=operation,
                possible=False,
                proof=None,
                complete=True,
                reasons=tuple(_dedupe(reasons)),
                provider_results=provider_results,
                explored_candidates=explored,
                optimal=True,
            )
        else:
            evidence = OperationEvidence(
                operation=operation,
                possible=None,
                proof=None,
                complete=False,
                reasons=tuple(_dedupe(reasons)),
                provider_results=provider_results,
                explored_candidates=explored,
                optimal=False,
            )

        self._operation_cache[cache_key] = evidence
        return evidence

    def _evaluate_candidate_min(
        self,
        goal: Goal[ShapeT],
        state: _ProviderEvaluationState[ShapeT],
        ordinal: int,
        candidate: InverseCandidate[ShapeT],
    ) -> _CandidateOutcome[ShapeT]:
        key = CandidateCacheKey(state.key, ordinal)
        cached = self._candidate_min_cache.get(key)
        if cached is not None:
            self.instrumentation.candidate_cache_hits[f"min_cost:{state.relation.provider_id}"] += 1
            return cached

        exists_cached = self._candidate_exists_cache.get(key)
        if exists_cached is not None and exists_cached.status is not ProofStatus.POSSIBLE:
            self._candidate_min_cache[key] = exists_cached
            return exists_cached

        self._validate_candidate_contract(goal, state, key, candidate)
        child_proofs: list[ProofNode[ShapeT]] = []
        unknown_reasons: list[str] = []
        children_optimal = True
        for child in candidate.children:
            child_goal = self._child_goal(goal, child)
            self.instrumentation.trace(
                "subgoal",
                self._goal_label(goal),
                self._goal_label(child_goal),
                child.role,
            )
            result = self.solve_min_cost(child_goal)
            if result.status is ProofStatus.IMPOSSIBLE:
                outcome = _CandidateOutcome(ProofStatus.IMPOSSIBLE, None, optimal=True)
                self._candidate_min_cache[key] = outcome
                return outcome
            if result.status is ProofStatus.UNKNOWN:
                unknown_reasons.extend(result.reasons or (f"unknown child: {child.role}",))
                children_optimal = False
            elif result.proof is not None:
                child_proofs.append(result.proof)
                children_optimal = children_optimal and result.optimal

        if unknown_reasons:
            outcome = _CandidateOutcome(
                ProofStatus.UNKNOWN,
                None,
                tuple(_dedupe(unknown_reasons)),
                optimal=False,
            )
            self._candidate_min_cache[key] = outcome
            return outcome

        replay_ok, replay_reason = self._verify_candidate_replay(goal, state, key, candidate)
        if replay_ok is not True:
            outcome = _CandidateOutcome(
                ProofStatus.UNKNOWN,
                None,
                (replay_reason or "forward replay unavailable",),
                optimal=False,
            )
            self._candidate_min_cache[key] = outcome
            return outcome

        proofs = tuple(child_proofs)
        total_cost = self.cost_model.combine(
            candidate.local_cost,
            tuple(child.total_cost for child in proofs),
        )
        node = self._build_proof(goal, candidate, proofs, total_cost)
        outcome = _CandidateOutcome(
            ProofStatus.POSSIBLE,
            node,
            optimal=children_optimal,
        )
        self._candidate_min_cache[key] = outcome
        return outcome

    # ------------------------------------------------------------------
    # Validation, replay, cost and helpers
    # ------------------------------------------------------------------
    def _validate_candidate_contract(
        self,
        goal: Goal[ShapeT],
        state: _ProviderEvaluationState[ShapeT],
        key: CandidateCacheKey,
        candidate: InverseCandidate[ShapeT],
    ) -> None:
        if key in self._candidate_contract_validated:
            return
        relation = state.relation
        if candidate.operation is not relation.operation:
            state.trusted = False
            self.instrumentation.rank_contract_failures += 1
            raise PlannerContractError(
                f"{relation.provider_id}: candidate operation {candidate.operation} != {relation.operation}"
            )
        if self.config.verify_candidate_targets and not self.backend.equal(
            self.backend.canonicalize(candidate.target), goal.shape
        ):
            state.trusted = False
            self.instrumentation.rank_contract_failures += 1
            raise PlannerContractError(f"{relation.provider_id}: candidate target mismatch")
        for child in candidate.children:
            if not goal.progress.allows(child.progress):
                state.trusted = False
                self.instrumentation.rank_contract_failures += 1
                raise PlannerContractError(
                    f"{relation.provider_id}: non-decreasing progress "
                    f"{child.progress.components} from {goal.progress.components}"
                )
        self._candidate_contract_validated.add(key)

    def _verify_candidate_replay(
        self,
        goal: Goal[ShapeT],
        state: _ProviderEvaluationState[ShapeT],
        key: CandidateCacheKey,
        candidate: InverseCandidate[ShapeT],
    ) -> tuple[bool | None, str]:
        cached = self._replay_cache.get(key)
        if cached is not None:
            return cached
        if self.forward is None:
            if self.config.require_forward_replay:
                result = (None, "forward replay model is not configured")
                self._replay_cache[key] = result
                state.trusted = False
                return result
            result = (True, "forward replay disabled by compatibility configuration")
            self._replay_cache[key] = result
            return result

        self.instrumentation.replay_validations += 1
        try:
            replayed = self.forward.replay(
                candidate.operation,
                tuple(child.shape for child in candidate.children),
                candidate.certificate,
            )
            valid = self.backend.equal(
                self.backend.canonicalize(replayed),
                goal.shape,
            )
            if not valid:
                self.instrumentation.replay_failures += 1
                state.trusted = False
                state.diagnostics[f"replay_failure_{key.ordinal}"] = "forward replay did not equal target"
                result = (False, "forward replay did not equal target")
            else:
                result = (True, "")
        except Exception as exc:
            self.instrumentation.replay_failures += 1
            state.trusted = False
            state.diagnostics[f"replay_exception_{key.ordinal}"] = f"{exc.__class__.__name__}: {exc}"
            result = (None, f"forward replay exception: {exc}")
        self._replay_cache[key] = result
        return result

    def _build_proof(
        self,
        goal: Goal[ShapeT],
        candidate: InverseCandidate[ShapeT],
        children: tuple[ProofNode[ShapeT], ...],
        total_cost: CostVector,
    ) -> ProofNode[ShapeT]:
        return ProofNode(
            shape=goal.shape,
            shape_key=self.backend.key(goal.shape),
            shape_code=self.backend.to_code(goal.shape),
            progress=goal.progress,
            operation=candidate.operation,
            children=children,
            certificate=candidate.certificate,
            local_cost=candidate.local_cost,
            total_cost=total_cost,
            traits=candidate.traits,
            metadata=candidate.metadata,
        )

    def _choose_better(
        self,
        current: _BestChoice[ShapeT] | None,
        challenger: _BestChoice[ShapeT],
    ) -> _BestChoice[ShapeT]:
        if current is None:
            return challenger
        self.instrumentation.proof_comparisons += 1
        if self._choice_key(challenger) < self._choice_key(current):
            return challenger
        return current

    def _choice_key(self, choice: _BestChoice[ShapeT]) -> tuple[Any, ...]:
        return (
            self.cost_model.ordering_key(choice.proof.total_cost),
            choice.proof.operation.value,
            choice.provider_id,
            choice.ordinal,
            tuple(child.shape_key for child in choice.proof.children),
        )

    def _provider_lower_bound(
        self,
        relation: InverseRelation[ShapeT],
        goal: Goal[ShapeT],
    ) -> CostVector:
        callback = getattr(relation, "admissible_lower_bound", None)
        if callback is None:
            return CostVector()
        try:
            result = callback(goal)
            return result if isinstance(result, CostVector) else CostVector()
        except Exception:
            return CostVector()

    def _child_goal(self, parent: Goal[ShapeT], child) -> Goal[ShapeT]:
        return self._canonical_goal(
            Goal(
                child.shape,
                child.progress,
                child.family_context or parent.family_context,
            )
        )

    def _missing_configuration_reasons(self) -> tuple[str, ...]:
        missing = self.registry.missing_required_relations(self.config.required_relation_ids)
        missing_operations = frozenset(
            operation
            for operation in self.config.required_operations
            if not self.registry.relations_for(operation)
        )
        reasons = [f"missing relation provider: {item}" for item in sorted(missing)]
        reasons.extend(
            f"missing provider for required operation: {operation.value}"
            for operation in sorted(missing_operations, key=lambda item: item.value)
        )
        return tuple(reasons)

    @staticmethod
    def _provider_incomplete_reason(state: _ProviderEvaluationState[ShapeT]) -> str:
        return (
            f"{state.relation.provider_id} partial/untrusted: "
            f"{state.coverage.reason or state.diagnostics or 'unspecified'}"
        )

    def _goal_label(self, goal: Goal[ShapeT]) -> str:
        return (
            f"goal:{self.backend.key(goal.shape)}@{goal.progress.components}"
            f"#{goal.family_context.context_id}"
        )


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output
