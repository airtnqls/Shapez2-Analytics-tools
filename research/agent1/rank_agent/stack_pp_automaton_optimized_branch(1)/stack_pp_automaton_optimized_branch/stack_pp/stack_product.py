from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Generic, Hashable, Iterator, Sequence, TypeVar

from .protocols import LayerFamilyAutomaton, TopPiecePolicy
from .rows import ADJACENT, RowInfo, landing_row_is_valid
from .top_policy import AnyTopPiecePolicy

FamilyStateT = TypeVar("FamilyStateT", bound=Hashable)
_INF = 10**18
_EMPTY_SUPPORT_BEHAVIOR: tuple[int, ...] = (16,) * 16


@lru_cache(maxsize=256)
def _horizontal_support_closure(nonpin_mask: int, seed_mask: int) -> int:
    supported = seed_mask & 15
    while True:
        before = supported
        for q in range(4):
            bit = 1 << q
            if not (supported & bit and nonpin_mask & bit):
                continue
            for neighbor in ADJACENT[q]:
                nbit = 1 << neighbor
                if nonpin_mask & nbit:
                    supported |= nbit
        if supported == before:
            return supported


@lru_cache(maxsize=131072)
def _advance_support_behavior(
    previous: tuple[int, ...],
    previous_occupied: int,
    previous_crystal: int,
    current_occupied: int,
    current_crystal: int,
    current_pin: int,
    is_floor: bool,
) -> tuple[int, ...]:
    """Exact width-four support transducer composition for one A row."""

    current_nonpin = current_occupied & ~current_pin & 15
    normalized: dict[int, int] = {}
    for injection_mask in range(16):
        injection = injection_mask & current_crystal
        if injection in normalized:
            continue
        current_supported = _horizontal_support_closure(
            current_nonpin,
            injection | (current_occupied if is_floor else 0),
        )
        while True:
            previous_injection = current_supported & current_crystal & previous_crystal
            previous_code = previous[previous_injection]
            previous_supported = previous_code & 15
            expanded = _horizontal_support_closure(
                current_nonpin,
                current_supported | (previous_supported & current_occupied),
            )
            if expanded == current_supported:
                break
            current_supported = expanded
        previous_injection = current_supported & current_crystal & previous_crystal
        previous_code = previous[previous_injection]
        previous_supported = previous_code & 15
        forgotten_supported = bool(previous_code & 16) and (
            previous_supported & previous_occupied
        ) == previous_occupied
        normalized[injection] = current_supported | (16 if forgotten_supported else 0)
    return tuple(normalized[injection & current_crystal] for injection in range(16))


def _support_behavior_accepts(behavior: tuple[int, ...], boundary_occupied: int) -> bool:
    code = behavior[0]
    return bool(code & 16) and (code & 15) == boundary_occupied


_GLOBAL_BEHAVIORS: list[tuple[int, ...]] = [_EMPTY_SUPPORT_BEHAVIOR]
_GLOBAL_BEHAVIOR_IDS: dict[tuple[int, ...], int] = {_EMPTY_SUPPORT_BEHAVIOR: 0}
_GLOBAL_BEHAVIOR_LOCK = Lock()


def _intern_behavior(behavior: tuple[int, ...]) -> int:
    found = _GLOBAL_BEHAVIOR_IDS.get(behavior)
    if found is not None:
        return found
    with _GLOBAL_BEHAVIOR_LOCK:
        found = _GLOBAL_BEHAVIOR_IDS.get(behavior)
        if found is not None:
            return found
        found = len(_GLOBAL_BEHAVIORS)
        _GLOBAL_BEHAVIORS.append(behavior)
        _GLOBAL_BEHAVIOR_IDS[behavior] = found
        return found


@lru_cache(maxsize=262144)
def _advance_behavior_id(
    previous_id: int,
    previous_occupied: int,
    previous_crystal: int,
    current_occupied: int,
    current_crystal: int,
    current_pin: int,
    is_floor: bool,
) -> int:
    return _intern_behavior(
        _advance_support_behavior(
            _GLOBAL_BEHAVIORS[previous_id],
            previous_occupied,
            previous_crystal,
            current_occupied,
            current_crystal,
            current_pin,
            is_floor,
        )
    )


def _pack_stable_state(switched: int, behavior_id: int, has_a: bool) -> int:
    return switched | (int(has_a) << 4) | (behavior_id << 5)


def _switched(state: int) -> int:
    return state & 15


def _has_a(state: int) -> bool:
    return bool(state & 16)


def _behavior_id(state: int) -> int:
    return state >> 5


def _local_product_edges(
    *,
    stable_state: int,
    family_state: FamilyStateT,
    row: RowInfo,
    previous_target: RowInfo,
    is_floor: bool,
    family: LayerFamilyAutomaton[FamilyStateT],
    top_policy: TopPiecePolicy,
) -> tuple["ProductEdge[FamilyStateT]", ...]:
    """Shared exact transition used by target DAG and closure automaton."""

    switched = _switched(stable_state)
    if switched & row.crystal:
        return ()
    previous_occupied = previous_target.occupied & ~switched & 15
    previous_crystal = previous_target.crystal & ~switched & 15
    startable = row.occupied & ~row.crystal & ~switched & 15
    subset = startable
    out: list[ProductEdge[FamilyStateT]] = []
    while True:
        next_mask = switched | subset
        b_mask = row.occupied & next_mask
        if landing_row_is_valid(
            is_floor=is_floor,
            b_mask=b_mask,
            row=row,
            below_occupied=previous_target.occupied,
        ):
            b_row = row.project(next_mask)
            if b_row.occupied and not top_policy.accepts(b_row.as_signature()):
                pass
            else:
                a_row = row.project(~next_mask & 15)
                next_family = family_state
                if a_row.occupied:
                    advanced = family.advance(family_state, a_row.as_signature())
                    if advanced is not None:
                        next_family = advanced
                    else:
                        next_family = None
                if next_family is not None:
                    next_behavior = _advance_behavior_id(
                        _behavior_id(stable_state),
                        previous_occupied,
                        previous_crystal,
                        a_row.occupied,
                        a_row.crystal,
                        a_row.pin,
                        is_floor,
                    )
                    next_stable = _pack_stable_state(
                        next_mask,
                        next_behavior,
                        _has_a(stable_state) or bool(a_row.occupied),
                    )
                    out.append(
                        ProductEdge(
                            next_stable,
                            next_family,
                            next_mask,
                            b_mask,
                            subset,
                            b_mask.bit_count(),
                        )
                    )
        if subset == 0:
            break
        subset = (subset - 1) & startable
    return tuple(out)


@dataclass(frozen=True)
class ProductEdge(Generic[FamilyStateT]):
    next_stable_state: int
    next_family_state: FamilyStateT
    ownership_mask: int
    b_mask: int
    started_mask: int
    visible_top_cost: int


@dataclass(frozen=True)
class StackProductStatistics:
    layers: int
    reachable_nodes: int
    viable_edges: int
    path_count: int
    support_behaviors_seen: int


class StackFamilyProductDAG(Generic[FamilyStateT]):
    """Exact Stack frontier intersected with a deterministic bottom family.

    It returns ownership paths only.  ``core-kernel`` later materializes the
    base and layer-piece proof from the path, keeping this module independent
    from any concrete Shape representation.
    """

    def __init__(
        self,
        rows: Sequence[RowInfo],
        family: LayerFamilyAutomaton[FamilyStateT],
        top_policy: TopPiecePolicy | None = None,
    ):
        self.rows = tuple(rows)
        self.height = len(self.rows)
        self.family = family
        self.top_policy = top_policy or AnyTopPiecePolicy()
        self.start = (_pack_stable_state(0, 0, False), family.start_state())
        self._states_by_layer: list[list[tuple[int, FamilyStateT]]] = [
            [] for _ in range(self.height + 1)
        ]
        self._state_sets_by_layer: list[set[tuple[int, FamilyStateT]]] = [
            set() for _ in range(self.height + 1)
        ]
        self._states_by_layer[0].append(self.start)
        self._state_sets_by_layer[0].add(self.start)
        self._all_edges: dict[
            tuple[int, tuple[int, FamilyStateT]], tuple[ProductEdge[FamilyStateT], ...]
        ] = {}
        self._edges: dict[
            tuple[int, tuple[int, FamilyStateT]], tuple[ProductEdge[FamilyStateT], ...]
        ] = {}
        self._viable: list[set[tuple[int, FamilyStateT]]] = [
            set() for _ in range(self.height + 1)
        ]
        self._best_cost: dict[tuple[int, tuple[int, FamilyStateT]], int] = {}
        self._path_count: dict[tuple[int, tuple[int, FamilyStateT]], int] = {}
        self._build_forward()
        self._build_backward()

    def _local_edges(
        self,
        layer: int,
        state: tuple[int, FamilyStateT],
    ) -> tuple[ProductEdge[FamilyStateT], ...]:
        stable_state, family_state = state
        previous_target = (
            self.rows[layer - 1] if layer > 0 else RowInfo(0, 0, 0, 0)
        )
        return _local_product_edges(
            stable_state=stable_state,
            family_state=family_state,
            row=self.rows[layer],
            previous_target=previous_target,
            is_floor=layer == 0,
            family=self.family,
            top_policy=self.top_policy,
        )

    def _build_forward(self) -> None:
        for layer in range(self.height):
            for state in self._states_by_layer[layer]:
                edges = self._local_edges(layer, state)
                self._all_edges[(layer, state)] = edges
                for edge in edges:
                    next_state = (edge.next_stable_state, edge.next_family_state)
                    if next_state in self._state_sets_by_layer[layer + 1]:
                        continue
                    self._state_sets_by_layer[layer + 1].add(next_state)
                    self._states_by_layer[layer + 1].append(next_state)

    def _terminal_accepts(self, state: tuple[int, FamilyStateT]) -> bool:
        stable_state, family_state = state
        switched = _switched(stable_state)
        if switched == 0 or not _has_a(stable_state):
            return False
        boundary = self.rows[-1].occupied & ~switched if self.rows else 0
        return (
            _support_behavior_accepts(
                _GLOBAL_BEHAVIORS[_behavior_id(stable_state)], boundary
            )
            and self.family.accepts(family_state)
        )

    def _build_backward(self) -> None:
        for state in self._states_by_layer[self.height]:
            if self._terminal_accepts(state):
                self._viable[self.height].add(state)
                self._best_cost[(self.height, state)] = 0
                self._path_count[(self.height, state)] = 1
        for layer in range(self.height - 1, -1, -1):
            next_viable = self._viable[layer + 1]
            for state in self._states_by_layer[layer]:
                edges = tuple(
                    sorted(
                        (
                            edge
                            for edge in self._all_edges.get((layer, state), ())
                            if (edge.next_stable_state, edge.next_family_state)
                            in next_viable
                        ),
                        key=lambda edge: (
                            edge.visible_top_cost,
                            edge.started_mask.bit_count(),
                            edge.ownership_mask,
                            edge.next_stable_state,
                            repr(edge.next_family_state),
                        ),
                    )
                )
                self._edges[(layer, state)] = edges
                if not edges:
                    continue
                self._viable[layer].add(state)
                self._best_cost[(layer, state)] = min(
                    edge.visible_top_cost
                    + self._best_cost[
                        (
                            layer + 1,
                            (edge.next_stable_state, edge.next_family_state),
                        )
                    ]
                    for edge in edges
                )
                self._path_count[(layer, state)] = sum(
                    self._path_count[
                        (
                            layer + 1,
                            (edge.next_stable_state, edge.next_family_state),
                        )
                    ]
                    for edge in edges
                )

    def exists(self) -> bool:
        return self.start in self._viable[0]

    def path_count(self) -> int:
        return self._path_count.get((0, self.start), 0)

    def best_path(self) -> tuple[int, ...] | None:
        if not self.exists():
            return None
        state = self.start
        path: list[int] = []
        for layer in range(self.height):
            edges = self._edges.get((layer, state), ())
            if not edges:
                return None
            edge = min(
                edges,
                key=lambda candidate: (
                    candidate.visible_top_cost
                    + self._best_cost[
                        (
                            layer + 1,
                            (
                                candidate.next_stable_state,
                                candidate.next_family_state,
                            ),
                        )
                    ],
                    candidate.visible_top_cost,
                    candidate.started_mask.bit_count(),
                    candidate.ownership_mask,
                ),
            )
            path.append(edge.ownership_mask)
            state = (edge.next_stable_state, edge.next_family_state)
        return tuple(path)

    def iter_paths(self) -> Iterator[tuple[int, ...]]:
        if not self.exists():
            return
        path: list[int] = []

        def visit(layer: int, state: tuple[int, FamilyStateT]):
            if layer == self.height:
                yield tuple(path)
                return
            for edge in self._edges.get((layer, state), ()):
                path.append(edge.ownership_mask)
                yield from visit(
                    layer + 1,
                    (edge.next_stable_state, edge.next_family_state),
                )
                path.pop()

        yield from visit(0, self.start)

    def statistics(self) -> StackProductStatistics:
        behavior_ids = {
            _behavior_id(stable)
            for layer_states in self._states_by_layer
            for stable, _family in layer_states
        }
        return StackProductStatistics(
            layers=self.height,
            reachable_nodes=sum(map(len, self._states_by_layer)),
            viable_edges=sum(map(len, self._edges.values())),
            path_count=self.path_count(),
            support_behaviors_seen=len(behavior_ids),
        )


@dataclass(frozen=True)
class StackClosureState(Generic[FamilyStateT]):
    """One deterministic powerset state of ``StackClosure(base_family)``."""

    last_row_signature: tuple[int, int, int, int] | None
    product_states: frozenset[tuple[int, FamilyStateT]]


class StackClosureAutomaton(Generic[FamilyStateT]):
    """Deterministic all-layer recognizer for a family-constrained Stack closure.

    If ``base_family`` has finitely many states, this construction is finite:
    it is the powerset determinization of the finite Stack-ownership/support ×
    base-family product.  The reachable state count may still be large, so
    minimization/state-growth analysis remains a separate research task.
    """

    def __init__(
        self,
        base_family: LayerFamilyAutomaton[FamilyStateT],
        top_policy: TopPiecePolicy | None = None,
        *,
        name: str | None = None,
    ) -> None:
        self.base_family = base_family
        self.top_policy = top_policy or AnyTopPiecePolicy()
        self.name = name or f"StackClosure({base_family.name})"
        start_product = (
            _pack_stable_state(0, 0, False),
            base_family.start_state(),
        )
        self._start = StackClosureState(None, frozenset({start_product}))
        self._transition_cache: dict[
            tuple[StackClosureState[FamilyStateT], tuple[int, int, int, int]],
            StackClosureState[FamilyStateT] | None,
        ] = {}

    def start_state(self) -> StackClosureState[FamilyStateT]:
        return self._start

    def advance(
        self,
        state: StackClosureState[FamilyStateT],
        row_signature: tuple[int, int, int, int],
    ) -> StackClosureState[FamilyStateT] | None:
        key = (state, row_signature)
        if key in self._transition_cache:
            return self._transition_cache[key]
        row = RowInfo(*row_signature)
        previous = (
            RowInfo(*state.last_row_signature)
            if state.last_row_signature is not None
            else RowInfo(0, 0, 0, 0)
        )
        next_states: set[tuple[int, FamilyStateT]] = set()
        is_floor = state.last_row_signature is None
        for stable_state, family_state in state.product_states:
            for edge in _local_product_edges(
                stable_state=stable_state,
                family_state=family_state,
                row=row,
                previous_target=previous,
                is_floor=is_floor,
                family=self.base_family,
                top_policy=self.top_policy,
            ):
                next_states.add(
                    (edge.next_stable_state, edge.next_family_state)
                )
        result = (
            StackClosureState(row_signature, frozenset(next_states))
            if next_states
            else None
        )
        self._transition_cache[key] = result
        return result

    def accepts(self, state: StackClosureState[FamilyStateT]) -> bool:
        if state.last_row_signature is None:
            return False
        final_occupied = state.last_row_signature[0]
        for stable_state, family_state in state.product_states:
            switched = _switched(stable_state)
            if switched == 0 or not _has_a(stable_state):
                continue
            boundary = final_occupied & ~switched & 15
            if (
                _support_behavior_accepts(
                    _GLOBAL_BEHAVIORS[_behavior_id(stable_state)], boundary
                )
                and self.base_family.accepts(family_state)
            ):
                return True
        return False

    def contains_rows(self, rows: Sequence[RowInfo]) -> bool:
        state: StackClosureState[FamilyStateT] | None = self.start_state()
        for row in rows:
            if state is None:
                return False
            state = self.advance(state, row.as_signature())
        return state is not None and self.accepts(state)

    def reachable_states(
        self,
        alphabet: Sequence[tuple[int, int, int, int]],
        max_layers: int,
    ) -> tuple[frozenset[StackClosureState[FamilyStateT]], ...]:
        """Explore reachable deterministic states for finite-state diagnostics."""

        levels: list[frozenset[StackClosureState[FamilyStateT]]] = [
            frozenset({self.start_state()})
        ]
        current = set(levels[0])
        for _ in range(max_layers):
            nxt: set[StackClosureState[FamilyStateT]] = set()
            for state in current:
                for row in alphabet:
                    result = self.advance(state, row)
                    if result is not None:
                        nxt.add(result)
            levels.append(frozenset(nxt))
            current = nxt
            if not current:
                break
        return tuple(levels)


@dataclass
class FamilyProductStackBackend(Generic[FamilyStateT]):
    """Raw-backend adapter that executes the family product before materializing."""

    family: object
    materializer: object
    top_policy: object | None = None

    def candidates(self, target):
        from .model import RawStackCandidate

        rows = self.materializer.rows(target)
        dag = StackFamilyProductDAG(rows, self.family, self.top_policy)
        for path in dag.iter_paths():
            raw = self.materializer.materialize(target, path)
            payload = {
                "ownership_path": path,
                "product_statistics": dag.statistics(),
                "materializer_payload": raw.payload,
                "bottom_family": self.family.name,
            }
            yield RawStackCandidate(
                raw.bottom,
                raw.top,
                payload,
                top_pieces=raw.top_pieces,
            )

# Stable name for differential testing after the optimized automaton becomes the
# public StackClosureAutomaton in stack_pp.__init__.
LegacyStackClosureAutomaton = StackClosureAutomaton
