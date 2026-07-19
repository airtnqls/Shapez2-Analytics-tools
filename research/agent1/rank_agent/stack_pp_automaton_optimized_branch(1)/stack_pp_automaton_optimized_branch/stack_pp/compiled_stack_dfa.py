from __future__ import annotations

"""Exact complete-DFA compilation and minimization for Stack closure."""

from array import array
from collections import deque, defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, Sequence
import sys

from .optimized_stack_closure import (
    AutomatonMetrics,
    SparseTransitionGroup,
    StackClosureAutomaton,
    StackClosureWitness,
)
from .row_table import ROW_COUNT, row_id_from_info, row_id_from_signature
from .rows import RowInfo


class AutomatonBuildLimitExceeded(RuntimeError):
    """A caller-imposed diagnostic guard fired; this is never an UNSAT result."""

    def __init__(self, observed_states: int, limit: int):
        super().__init__(
            f"explicit DFA build observed {observed_states} states, exceeding "
            f"the caller's diagnostic limit {limit}; membership remains unknown"
        )
        self.observed_states = observed_states
        self.limit = limit


@dataclass(frozen=True, slots=True)
class CompleteBuildMetrics:
    source_states: int
    source_transitions: int
    shortest_depth_counts: tuple[int, ...]
    minimized_states: int
    minimized_transitions: int
    dense_semantic_transitions: int
    alphabet_classes: int
    minimized_action_groups: int
    build_seconds: float
    minimize_seconds: float
    memory_bytes: int


class MinimizedStackClosureDFA:
    """A complete exact quotient of one fully explored Stack closure DFA.

    Witness reconstruction is deliberately delegated to the source lazy
    automaton.  The compiled table stores no parent history, so existence and
    high-volume membership stay compact.
    """

    def __init__(
        self,
        *,
        source: StackClosureAutomaton,
        start_state: int,
        transitions: tuple[array, ...],
        row_classes: bytes,
        accepting: tuple[bool, ...],
        action_groups: tuple[tuple[SparseTransitionGroup, ...], ...],
        metrics: CompleteBuildMetrics,
        name: str,
    ) -> None:
        self.source = source
        self._start = int(start_state)
        self._transitions = transitions
        self._row_classes = row_classes
        self._accepting = accepting
        self._action_groups = action_groups
        self._metrics = metrics
        self.name = name

    def start_state(self) -> int:
        return self._start

    def advance(self, state: int, row_signature: tuple[int, int, int, int]) -> int:
        return self.transition(state, row_id_from_signature(row_signature))

    def transition(self, state_id: int, row_id: int) -> int:
        return int(self._transitions[state_id][self._row_classes[row_id]])

    def accepts(self, state_or_shape) -> bool:
        if isinstance(state_or_shape, int) and 0 <= state_or_shape < len(self._accepting):
            return self._accepting[state_or_shape]
        return self.accepts_shape(state_or_shape)

    def accepts_state(self, state_id: int) -> bool:
        return self._accepting[state_id]

    def accepts_rows(self, rows: Sequence[RowInfo | tuple[int, int, int, int] | int]) -> bool:
        state = self._start
        for row in rows:
            if isinstance(row, int):
                row_id = row
            elif isinstance(row, RowInfo):
                row_id = row_id_from_info(row)
            else:
                row_id = row_id_from_signature(tuple(row))
            state = self.transition(state, row_id)
        return self._accepting[state]

    contains_rows = accepts_rows

    def accepts_shape(self, shape) -> bool:
        return self.source.accepts_shape(shape)

    def witness(self, shape_or_rows) -> StackClosureWitness | None:
        return self.source.witness(shape_or_rows)

    def transition_groups(self, state_id: int) -> tuple[SparseTransitionGroup, ...]:
        return self._action_groups[state_id]

    def metrics(self) -> CompleteBuildMetrics:
        return self._metrics

    def canonical_state(self, state_id: int) -> int:
        return int(state_id)

    def state_includes(self, left: int, right: int) -> bool:
        # Exact equality is always available.  Computing all residual language
        # inclusions of the minimized Stack DFA is optional future work.
        return left == right


def _deep_size(values: Iterable[object]) -> int:
    seen: set[int] = set()

    def visit(value) -> int:
        oid = id(value)
        if oid in seen:
            return 0
        seen.add(oid)
        total = sys.getsizeof(value)
        if isinstance(value, dict):
            total += sum(visit(k) + visit(v) for k, v in value.items())
        elif isinstance(value, (list, tuple, set, frozenset)):
            total += sum(visit(v) for v in value)
        return total

    return sum(visit(value) for value in values)


def compile_complete_minimized(
    automaton: StackClosureAutomaton,
    *,
    max_states: int | None = None,
    release_source_build_caches: bool = True,
    name: str | None = None,
) -> MinimizedStackClosureDFA:
    """Explore the complete reachable DFA and quotient exact future behavior.

    ``max_states`` is only a caller-side resource guard.  Exceeding it raises
    :class:`AutomatonBuildLimitExceeded`; callers must not interpret that as
    rejection or impossibility.
    """

    build_start = perf_counter()
    start = automaton.start_state()
    queue: deque[int] = deque([start])
    source_states: list[int] = [0, start]  # include dead state 0
    source_index = {0: 0, start: 1}
    source_depth = {0: -1, start: 0}
    dense_source: list[array | None] = [array("I", [0] * ROW_COUNT), None]

    while queue:
        source_state = queue.popleft()
        groups = automaton.transition_groups(source_state)
        dense = array("I", [0] * ROW_COUNT)
        for group in groups:
            target = group.next_state
            target_index = source_index.get(target)
            if target_index is None:
                target_index = len(source_states)
                source_index[target] = target_index
                source_states.append(target)
                dense_source.append(None)
                source_depth[target] = source_depth[source_state] + 1
                if max_states is not None and len(source_states) - 1 > max_states:
                    raise AutomatonBuildLimitExceeded(len(source_states) - 1, max_states)
                if target != 0:
                    queue.append(target)
            bits = group.row_mask
            while bits:
                bit = bits & -bits
                row_id = bit.bit_length() - 1
                bits -= bit
                dense[row_id] = target_index
        dense_source[source_index[source_state]] = dense

    assert all(row is not None for row in dense_source)
    source_table = tuple(row for row in dense_source if row is not None)
    source_accepting = tuple(
        False if state == 0 else automaton.accepts_state(state)
        for state in source_states
    )
    build_seconds = perf_counter() - build_start

    depth_counts_map: dict[int, int] = defaultdict(int)
    for state, depth in source_depth.items():
        if state != 0:
            depth_counts_map[depth] += 1
    shortest_depth_counts = tuple(
        depth_counts_map[depth]
        for depth in range(max(depth_counts_map, default=-1) + 1)
    )

    minimize_start = perf_counter()
    partition = [int(accepted) for accepted in source_accepting]
    while True:
        signature_to_block: dict[tuple, int] = {}
        refined: list[int] = []
        for state_id, row in enumerate(source_table):
            signature = (
                partition[state_id],
                tuple(partition[target] for target in row),
            )
            refined.append(
                signature_to_block.setdefault(signature, len(signature_to_block))
            )
        if refined == partition:
            break
        partition = refined

    block_count = max(partition) + 1
    representatives: list[int | None] = [None] * block_count
    for source_id, block in enumerate(partition):
        if representatives[block] is None:
            representatives[block] = source_id

    dense_minimized_table = tuple(
        tuple(partition[target] for target in source_table[rep])
        for rep in representatives
        if rep is not None
    )

    # Exact global alphabet quotient: two rows share a class iff every
    # minimized state has the same target under both.  This is a proven action
    # equivalence, not a structural guess about NORMAL/PIN/CRYSTAL.
    action_to_class: dict[tuple[int, ...], int] = {}
    row_classes_list: list[int] = []
    representatives_rows: list[int] = []
    for row_id in range(ROW_COUNT):
        signature = tuple(row[row_id] for row in dense_minimized_table)
        class_id = action_to_class.get(signature)
        if class_id is None:
            class_id = len(action_to_class)
            action_to_class[signature] = class_id
            representatives_rows.append(row_id)
        row_classes_list.append(class_id)
    row_classes = bytes(row_classes_list)
    minimized_table = tuple(
        array("I", (row[row_id] for row_id in representatives_rows))
        for row in dense_minimized_table
    )
    minimized_accepting = tuple(
        source_accepting[rep]
        for rep in representatives
        if rep is not None
    )
    minimized_groups: list[tuple[SparseTransitionGroup, ...]] = []
    for state_id, row in enumerate(minimized_table):
        grouped: dict[int, int] = defaultdict(int)
        for row_id in range(ROW_COUNT):
            target = row[row_classes[row_id]]
            grouped[int(target)] |= 1 << row_id
        minimized_groups.append(
            tuple(
                SparseTransitionGroup(target, row_mask)
                for target, row_mask in sorted(grouped.items())
            )
        )
    minimize_seconds = perf_counter() - minimize_start

    start_block = partition[source_index[start]]
    source_transition_count = len(source_table) * ROW_COUNT
    minimized_transition_count = len(minimized_table) * len(representatives_rows)
    dense_semantic_transition_count = len(minimized_table) * ROW_COUNT
    action_group_count = sum(len(groups) for groups in minimized_groups)
    memory = _deep_size(
        (minimized_table, row_classes, minimized_accepting, minimized_groups)
    )
    metrics = CompleteBuildMetrics(
        source_states=len(source_states) - 1,
        source_transitions=source_transition_count,
        shortest_depth_counts=shortest_depth_counts,
        minimized_states=block_count,
        minimized_transitions=minimized_transition_count,
        dense_semantic_transitions=dense_semantic_transition_count,
        alphabet_classes=len(representatives_rows),
        minimized_action_groups=action_group_count,
        build_seconds=build_seconds,
        minimize_seconds=minimize_seconds,
        memory_bytes=memory,
    )

    if release_source_build_caches:
        automaton.release_build_caches()

    return MinimizedStackClosureDFA(
        source=automaton,
        start_state=start_block,
        transitions=minimized_table,
        row_classes=row_classes,
        accepting=minimized_accepting,
        action_groups=tuple(minimized_groups),
        metrics=metrics,
        name=name or f"Minimized({automaton.name})",
    )
