from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from threading import RLock
from typing import Mapping

from .enums import SearchMode


@dataclass(frozen=True)
class PlannerMetricsSnapshot:
    provider_inverse_calls: Mapping[str, int]
    provider_cache_requests: int
    provider_cache_hits: int
    provider_cache_misses: int
    duplicate_provider_requests: int
    duplicate_provider_inverse_calls: int
    subgoal_solve_calls: Mapping[str, int]
    goal_cache_hits: Mapping[str, int]
    goal_cache_misses: Mapping[str, int]
    candidate_generated: Mapping[str, int]
    candidate_cache_hits: Mapping[str, int]
    replay_validations: int
    replay_failures: int
    cycle_blocks: int
    rank_contract_failures: int
    proof_comparisons: int
    branch_prunes: int
    negative_cache_hits: int
    provider_incomplete_events: int
    registry_invalidations: int
    max_recursion_depth: int
    trace_event_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    source: str
    target: str
    detail: str = ""


class PlannerInstrumentation:
    def __init__(self, *, trace_limit: int = 20_000) -> None:
        self.provider_inverse_calls: Counter[str] = Counter()
        self.provider_cache_requests = 0
        self.provider_cache_hits = 0
        self.provider_cache_misses = 0
        self.duplicate_provider_requests = 0
        self.provider_inverse_key_calls: Counter[str] = Counter()
        self.subgoal_solve_calls: Counter[str] = Counter()
        self.goal_cache_hits: Counter[str] = Counter()
        self.goal_cache_misses: Counter[str] = Counter()
        self.candidate_generated: Counter[str] = Counter()
        self.candidate_cache_hits: Counter[str] = Counter()
        self.replay_validations = 0
        self.replay_failures = 0
        self.cycle_blocks = 0
        self.rank_contract_failures = 0
        self.proof_comparisons = 0
        self.branch_prunes = 0
        self.negative_cache_hits = 0
        self.provider_incomplete_events = 0
        self.registry_invalidations = 0
        self.max_recursion_depth = 0
        self.trace_limit = trace_limit
        self.trace_events: list[TraceEvent] = []
        self._lock = RLock()

    def reset(self) -> None:
        trace_limit = self.trace_limit
        self.__init__(trace_limit=trace_limit)

    def record_goal_call(self, mode: SearchMode, goal_label: str, depth: int) -> None:
        with self._lock:
            self.subgoal_solve_calls[f"{mode.value}:{goal_label}"] += 1
            self.max_recursion_depth = max(self.max_recursion_depth, depth)

    def trace(self, kind: str, source: str, target: str, detail: str = "") -> None:
        with self._lock:
            if len(self.trace_events) < self.trace_limit:
                self.trace_events.append(TraceEvent(kind, source, target, detail))

    def snapshot(self) -> PlannerMetricsSnapshot:
        with self._lock:
            return PlannerMetricsSnapshot(
                provider_inverse_calls=dict(self.provider_inverse_calls),
                provider_cache_requests=self.provider_cache_requests,
                provider_cache_hits=self.provider_cache_hits,
                provider_cache_misses=self.provider_cache_misses,
                duplicate_provider_requests=self.duplicate_provider_requests,
                duplicate_provider_inverse_calls=sum(
                    max(0, count - 1) for count in self.provider_inverse_key_calls.values()
                ),
                subgoal_solve_calls=dict(self.subgoal_solve_calls),
                goal_cache_hits=dict(self.goal_cache_hits),
                goal_cache_misses=dict(self.goal_cache_misses),
                candidate_generated=dict(self.candidate_generated),
                candidate_cache_hits=dict(self.candidate_cache_hits),
                replay_validations=self.replay_validations,
                replay_failures=self.replay_failures,
                cycle_blocks=self.cycle_blocks,
                rank_contract_failures=self.rank_contract_failures,
                proof_comparisons=self.proof_comparisons,
                branch_prunes=self.branch_prunes,
                negative_cache_hits=self.negative_cache_hits,
                provider_incomplete_events=self.provider_incomplete_events,
                registry_invalidations=self.registry_invalidations,
                max_recursion_depth=self.max_recursion_depth,
                trace_event_count=len(self.trace_events),
            )

    def call_graph_dot(self) -> str:
        with self._lock:
            lines = ["digraph TMAMPlanner {", "  rankdir=LR;"]
            seen: set[tuple[str, str, str, str]] = set()
            for event in self.trace_events:
                key = (event.kind, event.source, event.target, event.detail)
                if key in seen:
                    continue
                seen.add(key)
                label = event.kind if not event.detail else f"{event.kind}: {event.detail}"
                source = event.source.replace('"', "\\\"")
                target = event.target.replace('"', "\\\"")
                label = label.replace('"', "\\\"")
                lines.append(f'  "{source}" -> "{target}" [label="{label}"];')
            lines.append("}")
            return "\n".join(lines) + "\n"
