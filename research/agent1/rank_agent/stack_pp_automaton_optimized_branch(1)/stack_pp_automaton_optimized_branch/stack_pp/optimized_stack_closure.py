from __future__ import annotations

"""Memory-controlled exact Stack-closure automaton.

This module preserves the complete relation implemented by the legacy
``StackClosureAutomaton`` while avoiding its hash-heavy
``frozenset[(support_history, family_state)]`` representation.

The important exact quotients are:

* the width-four support transducer is minimized by complete DFA residual
  language equivalence (generated in :mod:`stack_pp.support_quotient`);
* deterministic subsets are normalized to a language-inclusion antichain;
* family states may opt into their own proved canonicalization/inclusion hooks;
* the previous target row keeps only its occupied mask, because crystal/support
  history is already internal to the minimized support state;
* states, family states, products, and subsets are interned as compact integer
  ids; transitions are generated lazily and may be stored as exact row-action
  equivalence groups.

No state cap or timeout changes the answer.  ``0`` is an internal dead state,
never an "impossible because resources ran out" result.
"""

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Generic, Hashable, Iterable, Iterator, Sequence, TypeVar
import sys

from .protocols import LayerFamilyAutomaton, TopPiecePolicy
from .row_table import (
    PROJECT_ROW_ID,
    ROW_COUNT,
    ROW_CRYSTAL,
    ROW_INFO,
    ROW_OCCUPIED,
    ROW_SIGNATURES,
    SUBMASKS,
    landing_valid,
    row_id_from_info,
    row_id_from_signature,
)
from .rows import RowInfo
from .support_quotient import (
    SUPPORT_ACCEPTING,
    SUPPORT_INCLUDES,
    SUPPORT_START,
    SUPPORT_STATE_COUNT,
    SUPPORT_TRANSITIONS,
)
from .top_policy import AnyTopPiecePolicy

FamilyStateT = TypeVar("FamilyStateT", bound=Hashable)
ShapeT = TypeVar("ShapeT")
_DEAD_STATE = 0
_START_PREVIOUS_OCCUPIED = 16
_START_SUPPORT = 255


@dataclass(frozen=True, slots=True)
class _ProductRecord:
    switched: int
    support_state: int
    has_a: bool
    family_id: int


@dataclass(frozen=True, slots=True)
class _DeterministicState:
    previous_occupied: int
    products: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SparseTransitionGroup:
    """All row ids in ``row_mask`` have the same exact target state."""

    next_state: int
    row_mask: int

    @property
    def row_count(self) -> int:
        return self.row_mask.bit_count()


@dataclass(frozen=True, slots=True)
class StackClosureWitness:
    """One accepted ownership path, reconstructed only on request."""

    ownership_path: tuple[int, ...]
    final_product_id: int
    final_family_state: object
    visible_top_pieces: int
    materialized: object | None = None
    replay_verified: bool = False


@dataclass(frozen=True, slots=True)
class AutomatonMetrics:
    reachable_states: int
    transitions: int
    peak_frontier: int
    memory_bytes: int
    build_seconds: float
    interned_products: int = 0
    interned_family_states: int = 0
    component_transition_entries: int = 0
    evaluated_row_transitions: int = 0
    sparse_transition_groups: int = 0
    dead_row_transitions: int = 0
    max_subset_size: int = 0
    support_states: int = SUPPORT_STATE_COUNT


@dataclass(frozen=True, slots=True)
class ExplorationMetrics:
    levels: tuple[frozenset[int], ...]
    states_per_exact_depth: tuple[int, ...]
    cumulative_states_per_depth: tuple[int, ...]
    transitions_per_depth: tuple[int, ...]
    peak_frontier: int
    seconds_per_depth: tuple[float, ...]


class StackClosureAutomaton(Generic[FamilyStateT, ShapeT]):
    """Exact lazy determinization of ``StackClosure(base_family)``.

    The object also implements ``LayerFamilyAutomaton``:

    * ``start_state()`` returns an integer state id;
    * ``advance(state, row_signature)`` returns another id or ``None``;
    * ``accepts(state_id)`` tests a family state.

    For user-facing membership use ``accepts_rows`` / ``accepts_shape``.  The
    overloaded ``accepts`` treats an integer as a family-state id and every
    other value as an input shape/row stream.
    """

    def __init__(
        self,
        base_family: LayerFamilyAutomaton[FamilyStateT],
        top_policy: TopPiecePolicy | None = None,
        *,
        name: str | None = None,
        row_reader: Callable[[ShapeT], Sequence[RowInfo | tuple[int, int, int, int] | int]] | None = None,
        materializer: object | None = None,
        replay_validator: Callable[[ShapeT, object], bool] | None = None,
        enable_subsumption: bool = True,
    ) -> None:
        self.base_family = base_family
        self.top_policy = top_policy or AnyTopPiecePolicy()
        self.name = name or f"StackClosure({base_family.name})"
        self.row_reader = row_reader
        self.materializer = materializer
        self.replay_validator = replay_validator
        self.enable_subsumption = bool(enable_subsumption)

        self._family_states: list[FamilyStateT] = []
        self._family_ids: dict[FamilyStateT, int] = {}
        self._family_transition_cache: dict[tuple[int, int], int] = {}
        self._family_inclusion_cache: dict[tuple[int, int], bool] = {}

        self._products: list[_ProductRecord] = []
        self._product_ids: dict[_ProductRecord, int] = {}
        # Packed cache key: product_id | previous occupancy | row id.
        # Packed edge: ``next_product_id << 4 | ownership_mask``.  b_mask,
        # started_mask and visible cost are derivable from the current row and
        # product, so storing Python dataclass objects would be pure overhead.
        self._component_transition_cache: dict[int, tuple[int, ...]] = {}

        # State 0 is dead.  Every live state has a parallel sparse cache and an
        # optional 256-symbol action grouping.
        self._states: list[_DeterministicState | None] = [None]
        self._state_ids: dict[_DeterministicState, int] = {}
        self._transition_cache: list[dict[int, int]] = [{}]
        self._action_groups: list[tuple[SparseTransitionGroup, ...] | None] = [None]
        self._accepting_cache: list[bool | None] = [False]

        self._build_seconds = 0.0
        self._evaluated_row_transitions = 0
        self._dead_row_transitions = 0
        self._peak_frontier = 1
        self._max_subset_size = 1

        start_family = self._intern_family_state(base_family.start_state())
        start_product = self._intern_product(
            _ProductRecord(0, _START_SUPPORT, False, start_family)
        )
        self._start_state = self._intern_state(
            _DeterministicState(_START_PREVIOUS_OCCUPIED, (start_product,))
        )

        self._top_allowed = tuple(
            True
            if ROW_OCCUPIED[row_id] == 0
            else bool(self.top_policy.accepts(ROW_SIGNATURES[row_id]))
            for row_id in range(ROW_COUNT)
        )

    # ------------------------------------------------------------------
    # LayerFamilyAutomaton surface
    # ------------------------------------------------------------------
    def start_state(self) -> int:
        return self._start_state

    def advance(
        self,
        state: int,
        row_signature: tuple[int, int, int, int],
    ) -> int | None:
        next_state = self.transition(state, row_id_from_signature(row_signature))
        return None if next_state == _DEAD_STATE else next_state

    def accepts(self, state_or_shape) -> bool:
        if isinstance(state_or_shape, int) and 0 <= state_or_shape < len(self._states):
            return self.accepts_state(state_or_shape)
        return self.accepts_shape(state_or_shape)

    def accepts_state(self, state_id: int) -> bool:
        if state_id == _DEAD_STATE:
            return False
        cached = self._accepting_cache[state_id]
        if cached is not None:
            return cached
        state = self._states[state_id]
        assert state is not None
        accepted = any(self._product_accepts(product_id) for product_id in state.products)
        self._accepting_cache[state_id] = accepted
        return accepted

    # Optional exact hooks consumed by a later family product.  Equality is
    # always sound; the full residual-inclusion relation of this potentially
    # huge lazy DFA is deliberately not guessed.
    def canonical_state(self, state_id: int) -> int:
        return int(state_id)

    def state_includes(self, left: int, right: int) -> bool:
        return left == right

    # ------------------------------------------------------------------
    # Public deterministic-state API
    # ------------------------------------------------------------------
    def transition(self, state_id: int, row_id: int) -> int:
        if state_id == _DEAD_STATE:
            return _DEAD_STATE
        if not 0 <= row_id < ROW_COUNT:
            raise ValueError(f"row id outside [0,255]: {row_id}")

        grouped = self._action_groups[state_id]
        if grouped is not None:
            bit = 1 << row_id
            for group in grouped:
                if group.row_mask & bit:
                    return group.next_state
            raise AssertionError("row missing from a complete action grouping")

        cached = self._transition_cache[state_id].get(row_id)
        if cached is not None:
            return cached
        start = perf_counter()
        result = self._compute_transition(state_id, row_id)
        self._build_seconds += perf_counter() - start
        self._transition_cache[state_id][row_id] = result
        return result

    def transition_groups(self, state_id: int) -> tuple[SparseTransitionGroup, ...]:
        """Return exact state-local row action equivalence classes.

        Rows are merged only after all 256 exact transitions have been
        evaluated and found to lead to the same normalized state id.  This is a
        transition-storage quotient, not an assumed global alphabet quotient.
        """

        if state_id == _DEAD_STATE:
            return (SparseTransitionGroup(_DEAD_STATE, (1 << ROW_COUNT) - 1),)
        existing = self._action_groups[state_id]
        if existing is not None:
            return existing

        start = perf_counter()
        grouped: dict[int, int] = defaultdict(int)
        for row_id in range(ROW_COUNT):
            result = self._transition_cache[state_id].get(row_id)
            if result is None:
                result = self._compute_transition(state_id, row_id)
            grouped[result] |= 1 << row_id
        groups = tuple(
            SparseTransitionGroup(next_state, row_mask)
            for next_state, row_mask in sorted(grouped.items())
        )
        self._action_groups[state_id] = groups
        # The grouped table is complete, so retaining 256 individual dict
        # entries would be pure duplication.
        self._transition_cache[state_id].clear()
        self._build_seconds += perf_counter() - start
        return groups

    def release_build_caches(self) -> None:
        """Release local-construction caches after a full DFA build.

        State ids and exact state-level action groups remain valid.  Future
        transitions from an already grouped state need no component cache; if a
        new unseen state is queried later, its component edges are recomputed.
        """

        self._component_transition_cache.clear()
        self._family_transition_cache.clear()
        self._family_inclusion_cache.clear()

    def metrics(self) -> AutomatonMetrics:
        sparse_entries = sum(len(cache) for cache in self._transition_cache)
        action_groups = sum(
            len(groups) for groups in self._action_groups if groups is not None
        )
        return AutomatonMetrics(
            reachable_states=len(self._states) - 1,
            transitions=sparse_entries + action_groups,
            peak_frontier=self._peak_frontier,
            memory_bytes=self._memory_bytes(),
            build_seconds=self._build_seconds,
            interned_products=len(self._products),
            interned_family_states=len(self._family_states),
            component_transition_entries=len(self._component_transition_cache),
            evaluated_row_transitions=self._evaluated_row_transitions,
            sparse_transition_groups=action_groups,
            dead_row_transitions=self._dead_row_transitions,
            max_subset_size=self._max_subset_size,
        )

    # ------------------------------------------------------------------
    # Membership and witness paths
    # ------------------------------------------------------------------
    def accepts_rows(
        self,
        rows: Sequence[RowInfo | tuple[int, int, int, int] | int],
    ) -> bool:
        state = self._start_state
        for row_id in self._coerce_row_ids(rows):
            state = self.transition(state, row_id)
            if state == _DEAD_STATE:
                return False
        return self.accepts_state(state)

    contains_rows = accepts_rows

    def accepts_shape(self, shape: ShapeT) -> bool:
        return self.accepts_rows(self._read_rows(shape))

    def witness(
        self,
        shape_or_rows,
    ) -> StackClosureWitness | None:
        """Reconstruct one path without burdening ``accepts`` with history."""

        is_shape = not self._looks_like_rows(shape_or_rows)
        rows_source = self._read_rows(shape_or_rows) if is_shape else shape_or_rows
        row_ids = self._coerce_row_ids(rows_source)

        start_product = self._states[self._start_state].products[0]  # type: ignore[union-attr]
        current: tuple[int, ...] = (start_product,)
        previous_occupied = _START_PREVIOUS_OCCUPIED
        predecessor_layers: list[dict[int, tuple[int, int]]] = []
        costs: dict[int, int] = {start_product: 0}

        for row_id in row_ids:
            candidates: dict[int, tuple[int, int, int]] = {}
            for product_id in current:
                for packed_edge in self._component_edges(
                    product_id, previous_occupied, row_id
                ):
                    next_product_id = packed_edge >> 4
                    ownership_mask = packed_edge & 15
                    visible_cost = (
                        ROW_OCCUPIED[row_id] & ownership_mask
                    ).bit_count()
                    cost = costs[product_id] + visible_cost
                    old = candidates.get(next_product_id)
                    choice = (cost, product_id, ownership_mask)
                    if old is None or choice < old:
                        candidates[next_product_id] = choice
            if not candidates:
                return None
            surviving = self._normalize_products(candidates)
            layer_predecessor: dict[int, tuple[int, int]] = {}
            next_costs: dict[int, int] = {}
            for product_id in surviving:
                cost, previous_product, ownership = candidates[product_id]
                layer_predecessor[product_id] = (previous_product, ownership)
                next_costs[product_id] = cost
            predecessor_layers.append(layer_predecessor)
            current = surviving
            costs = next_costs
            previous_occupied = ROW_OCCUPIED[row_id]

        accepting = [product_id for product_id in current if self._product_accepts(product_id)]
        if not accepting:
            return None
        final_product = min(
            accepting,
            key=lambda product_id: (costs[product_id], self._product_sort_key(product_id)),
        )
        ownership_reversed: list[int] = []
        product_id = final_product
        for layer_predecessor in reversed(predecessor_layers):
            previous_product, ownership = layer_predecessor[product_id]
            ownership_reversed.append(ownership)
            product_id = previous_product
        ownership_path = tuple(reversed(ownership_reversed))

        final_record = self._products[final_product]
        materialized = None
        replay_verified = False
        if is_shape and self.materializer is not None:
            materialized = self.materializer.materialize(shape_or_rows, ownership_path)
            if self.replay_validator is not None:
                replay_verified = bool(
                    self.replay_validator(shape_or_rows, materialized)
                )
                if not replay_verified:
                    raise RuntimeError(
                        "StackClosure witness failed the supplied forward replay validator"
                    )

        return StackClosureWitness(
            ownership_path=ownership_path,
            final_product_id=final_product,
            final_family_state=self._family_states[final_record.family_id],
            visible_top_pieces=costs[final_product],
            materialized=materialized,
            replay_verified=replay_verified,
        )

    # ------------------------------------------------------------------
    # Reachability diagnostics / explicit lazy automaton building
    # ------------------------------------------------------------------
    def explore(
        self,
        max_layers: int,
        alphabet: Iterable[int] | None = None,
        *,
        group_full_alphabet: bool = True,
    ) -> ExplorationMetrics:
        if max_layers < 0:
            raise ValueError("max_layers must be nonnegative")
        alphabet_tuple = tuple(range(ROW_COUNT) if alphabet is None else alphabet)
        levels: list[frozenset[int]] = [frozenset({self._start_state})]
        current = set(levels[0])
        seen = set(current)
        state_counts = [len(current)]
        cumulative = [len(seen)]
        transition_counts: list[int] = []
        seconds: list[float] = []
        peak = len(current)

        full_alphabet = group_full_alphabet and alphabet_tuple == tuple(range(ROW_COUNT))
        for _depth in range(max_layers):
            t0 = perf_counter()
            nxt: set[int] = set()
            edge_count = 0
            for state_id in current:
                if full_alphabet:
                    groups = self.transition_groups(state_id)
                    edge_count += len(groups)
                    nxt.update(
                        group.next_state
                        for group in groups
                        if group.next_state != _DEAD_STATE
                    )
                else:
                    for row_id in alphabet_tuple:
                        edge_count += 1
                        result = self.transition(state_id, row_id)
                        if result != _DEAD_STATE:
                            nxt.add(result)
            seconds.append(perf_counter() - t0)
            transition_counts.append(edge_count)
            levels.append(frozenset(nxt))
            current = nxt
            seen.update(current)
            state_counts.append(len(current))
            cumulative.append(len(seen))
            peak = max(peak, len(current))
            self._peak_frontier = max(self._peak_frontier, peak)
            if not current:
                break

        return ExplorationMetrics(
            levels=tuple(levels),
            states_per_exact_depth=tuple(state_counts),
            cumulative_states_per_depth=tuple(cumulative),
            transitions_per_depth=tuple(transition_counts),
            peak_frontier=peak,
            seconds_per_depth=tuple(seconds),
        )

    def reachable_states(
        self,
        alphabet: Sequence[tuple[int, int, int, int]],
        max_layers: int,
    ) -> tuple[frozenset[int], ...]:
        row_ids = tuple(row_id_from_signature(row) for row in alphabet)
        return self.explore(
            max_layers,
            row_ids,
            group_full_alphabet=row_ids == tuple(range(ROW_COUNT)),
        ).levels

    # ------------------------------------------------------------------
    # Exact local/product normalization
    # ------------------------------------------------------------------
    def _compute_transition(self, state_id: int, row_id: int) -> int:
        self._evaluated_row_transitions += 1
        state = self._states[state_id]
        assert state is not None
        candidates: set[int] = set()
        for product_id in state.products:
            candidates.update(
                packed_edge >> 4
                for packed_edge in self._component_edges(
                    product_id, state.previous_occupied, row_id
                )
            )
        if not candidates:
            self._dead_row_transitions += 1
            return _DEAD_STATE
        products = self._normalize_products(candidates)
        return self._intern_state(
            _DeterministicState(ROW_OCCUPIED[row_id], products)
        )

    def _component_edges(
        self,
        product_id: int,
        previous_occupied: int,
        row_id: int,
    ) -> tuple[int, ...]:
        key = (product_id << 13) | (previous_occupied << 8) | row_id
        cached = self._component_transition_cache.get(key)
        if cached is not None:
            return cached

        record = self._products[product_id]
        row = ROW_INFO[row_id]
        if record.switched & row.crystal:
            self._component_transition_cache[key] = ()
            return ()

        is_floor = previous_occupied == _START_PREVIOUS_OCCUPIED
        below = 0 if is_floor else previous_occupied
        startable = row.occupied & ~row.crystal & ~record.switched & 15
        edges: list[int] = []
        for subset in SUBMASKS[startable]:
            next_switched = record.switched | subset
            b_mask = row.occupied & next_switched
            if not landing_valid(row_id, b_mask, below, is_floor):
                continue
            b_row_id = PROJECT_ROW_ID[row_id][next_switched]
            if ROW_OCCUPIED[b_row_id] and not self._top_allowed[b_row_id]:
                continue
            a_row_id = PROJECT_ROW_ID[row_id][~next_switched & 15]
            next_family = self._advance_family(record.family_id, a_row_id)
            if next_family < 0:
                continue
            next_support = (
                SUPPORT_START[a_row_id]
                if is_floor
                else SUPPORT_TRANSITIONS[record.support_state][a_row_id]
            )
            next_product = self._intern_product(
                _ProductRecord(
                    switched=next_switched,
                    support_state=next_support,
                    has_a=record.has_a or bool(ROW_OCCUPIED[a_row_id]),
                    family_id=next_family,
                )
            )
            edges.append((next_product << 4) | next_switched)
        result = tuple(edges)
        self._component_transition_cache[key] = result
        return result

    def _normalize_products(self, products: Iterable[int] | dict[int, object]) -> tuple[int, ...]:
        values = sorted(set(products), key=self._product_sort_key)
        if not self.enable_subsumption or len(values) < 2:
            result = tuple(values)
            self._max_subset_size = max(self._max_subset_size, len(result))
            return result

        maximal: list[int] = []
        for candidate in values:
            if any(self._product_includes(existing, candidate) for existing in maximal):
                continue
            maximal = [
                existing
                for existing in maximal
                if not self._product_includes(candidate, existing)
            ]
            maximal.append(candidate)
        result = tuple(sorted(maximal, key=self._product_sort_key))
        self._max_subset_size = max(self._max_subset_size, len(result))
        return result

    def _product_includes(self, left_id: int, right_id: int) -> bool:
        """Sound residual-language simulation used by the existential antichain."""

        left = self._products[left_id]
        right = self._products[right_id]

        # A path that switched fewer columns can emulate the other path by
        # switching each missing column at its next visible non-crystal cell.
        if left.switched & ~right.switched:
            return False
        # A past visible B piece cannot be invented by a path that has never
        # switched.  Once both are non-zero, the precise past B column is not
        # semantically relevant to future suffixes.
        if right.switched and not left.switched:
            return False
        if right.has_a and not left.has_a:
            return False
        if not (SUPPORT_INCLUDES[left.support_state] >> right.support_state) & 1:
            return False
        return self._family_state_includes(left.family_id, right.family_id)

    def _product_accepts(self, product_id: int) -> bool:
        record = self._products[product_id]
        return (
            record.switched != 0
            and record.has_a
            and SUPPORT_ACCEPTING[record.support_state]
            and bool(self.base_family.accepts(self._family_states[record.family_id]))
        )

    # ------------------------------------------------------------------
    # Interners and family quotient hooks
    # ------------------------------------------------------------------
    def _canonical_family_state(self, state: FamilyStateT) -> FamilyStateT:
        canonicalizer = getattr(self.base_family, "canonical_state", None)
        return canonicalizer(state) if canonicalizer is not None else state

    def _intern_family_state(self, state: FamilyStateT) -> int:
        state = self._canonical_family_state(state)
        found = self._family_ids.get(state)
        if found is not None:
            return found
        found = len(self._family_states)
        self._family_states.append(state)
        self._family_ids[state] = found
        return found

    def _advance_family(self, family_id: int, a_row_id: int) -> int:
        if ROW_OCCUPIED[a_row_id] == 0:
            return family_id
        key = (family_id, a_row_id)
        cached = self._family_transition_cache.get(key)
        if cached is not None:
            return cached
        next_state = self.base_family.advance(
            self._family_states[family_id], ROW_SIGNATURES[a_row_id]
        )
        result = -1 if next_state is None else self._intern_family_state(next_state)
        self._family_transition_cache[key] = result
        return result

    def _family_state_includes(self, left_id: int, right_id: int) -> bool:
        if left_id == right_id:
            return True
        key = (left_id, right_id)
        cached = self._family_inclusion_cache.get(key)
        if cached is not None:
            return cached
        includes = getattr(self.base_family, "state_includes", None)
        result = bool(
            includes(
                self._family_states[left_id], self._family_states[right_id]
            )
        ) if includes is not None else False
        self._family_inclusion_cache[key] = result
        return result

    def _intern_product(self, record: _ProductRecord) -> int:
        found = self._product_ids.get(record)
        if found is not None:
            return found
        found = len(self._products)
        self._products.append(record)
        self._product_ids[record] = found
        return found

    def _intern_state(self, state: _DeterministicState) -> int:
        found = self._state_ids.get(state)
        if found is not None:
            return found
        found = len(self._states)
        self._states.append(state)
        self._state_ids[state] = found
        self._transition_cache.append({})
        self._action_groups.append(None)
        self._accepting_cache.append(None)
        self._max_subset_size = max(self._max_subset_size, len(state.products))
        return found

    def _product_sort_key(self, product_id: int) -> tuple:
        record = self._products[product_id]
        return (
            record.switched.bit_count(),
            record.switched,
            -int(record.has_a),
            record.support_state,
            record.family_id,
        )

    # ------------------------------------------------------------------
    # Input conversion and memory diagnostics
    # ------------------------------------------------------------------
    def _looks_like_rows(self, value) -> bool:
        if isinstance(value, (str, bytes)):
            return False
        if not isinstance(value, Sequence):
            return False
        if not value:
            return True
        first = value[0]
        return isinstance(first, (int, RowInfo, tuple, list))

    def _read_rows(self, shape: ShapeT):
        if self.row_reader is None:
            raise TypeError(
                "this automaton has no row_reader; pass RowInfo/signature rows "
                "or construct it with row_reader=..."
            )
        return self.row_reader(shape)

    def _coerce_row_ids(
        self,
        rows: Sequence[RowInfo | tuple[int, int, int, int] | int],
    ) -> tuple[int, ...]:
        result: list[int] = []
        for row in rows:
            if isinstance(row, int):
                if not 0 <= row < ROW_COUNT:
                    raise ValueError(f"row id outside [0,255]: {row}")
                result.append(row)
            elif isinstance(row, RowInfo):
                result.append(row_id_from_info(row))
            else:
                result.append(row_id_from_signature(tuple(row)))
        return tuple(result)

    def _memory_bytes(self) -> int:
        """Conservative owned-container size; excludes shared generated tables."""

        seen: set[int] = set()

        def size(value) -> int:
            oid = id(value)
            if oid in seen:
                return 0
            seen.add(oid)
            total = sys.getsizeof(value)
            if isinstance(value, dict):
                total += sum(size(k) + size(v) for k, v in value.items())
            elif isinstance(value, (list, tuple, set, frozenset)):
                total += sum(size(item) for item in value)
            return total

        return sum(
            size(value)
            for value in (
                self._family_states,
                self._family_ids,
                self._family_transition_cache,
                self._family_inclusion_cache,
                self._products,
                self._product_ids,
                self._component_transition_cache,
                self._states,
                self._state_ids,
                self._transition_cache,
                self._action_groups,
                self._accepting_cache,
            )
        )
