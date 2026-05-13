from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import itertools
import struct
import random
import re
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CORNER_MAIN = PROJECT_ROOT / "corner_rule_test" / "main.py"
ALPHABET = ("S", "-", "P", "c")
SYMBOL_TO_CODE = {"-": 0, "S": 1, "P": 2, "c": 3}
CODE_TO_SYMBOL = {value: key for key, value in SYMBOL_TO_CODE.items()}
MAX_LAYERS = 5
TOKEN_RE = re.compile(r"^[A-Za-z:\-]+$")
LAYERS = tuple(a + b + c + d for a in ALPHABET for b in ALPHABET for c in ALPHABET for d in ALPHABET)
HYBRID_RESCUE_STATS: Counter[str] = Counter()
HYBRID_RESCUE_TIMES: Counter[str] = Counter()
CLAW_VERIFY_STATS: Counter[str] = Counter()
CLAW_VERIFY_TIMES: Counter[str] = Counter()
PP_INVERSE_STATS: Counter[str] = Counter()
TOP_LAYER_HYBRID_MISS_ONLY: frozenset[tuple[str, tuple[int, bool, str | None]]] = frozenset(
    {
        ("S-Sc", (1, True, None)),
        ("-ScS", (1, True, None)),
        ("--cS", (1, True, "swap_12_34_blocked")),
        ("-cS-", (1, True, "swap_14_23_blocked")),
        ("Sc--", (1, True, "swap_12_34_blocked")),
        ("--Sc", (1, True, "swap_12_34_blocked")),
        ("-Sc-", (1, True, "swap_14_23_blocked")),
        ("S--c", (1, True, "swap_14_23_blocked")),
        ("ScS-", (1, True, "swap_12_34_blocked")),
        ("ScS-", (1, True, "swap_14_23_blocked")),
        ("-ScS", (1, True, "swap_12_34_blocked")),
        ("cSPP", (1, True, "swap_12_34_blocked")),
        ("ScP-", (1, True, "swap_12_34_blocked")),
    }
)
SAFE_STACKABILITY_TOP_PEN_REMS: frozenset[tuple[str, str, tuple[int, bool, str | None]]] = frozenset(
    {
        ("cSS-", "S-SS", (2, True, "swap_12_34_blocked")),
        ("cSSS", "S-SS", (2, True, "swap_12_34_blocked")),
        ("cSSS", "SS--", (1, True, "swap_14_23_blocked")),
        ("c-S-", "SSSS", (2, True, "swap_12_34_blocked")),
        ("c---", "SSSS", (2, True, "swap_12_34_blocked")),
        ("c-SS", "SS-S", (1, True, "swap_12_34_blocked")),
        ("--SS", "cSSS", (2, True, "swap_12_34_blocked")),
        ("cSS-", "c-SS", (2, True, "swap_12_34_blocked")),
        ("cSS-", "cS-S", (1, True, "swap_14_23_blocked")),
        ("cSSS", "S--P", (1, True, "swap_12_34_blocked")),
    }
)
CLAW_PRIMITIVE_PREDECESSOR_TOP_PEN_REMS: frozenset[tuple[str, str, tuple[int, bool, str | None]]] = frozenset(
    {
        ("cS-S", "S-S-", (1, True, None)),
        ("cS-S", "c-S-", (1, True, None)),
        ("cS-S", "S---", (1, True, None)),
        ("cS-S", "c---", (1, True, None)),
    }
)
CLAW_HYBRID_MISS_ONLY_TOP_PEN_REMS: frozenset[tuple[str, str, tuple[int, bool, str | None]]] = frozenset(
    {
        ("cS-S", "-cS-", (1, True, None)),
        ("cS-S", "--Sc", (1, True, None)),
        ("cS-S", "S-Sc", (1, True, "swap_12_34_blocked")),
        ("cS--", "c-Sc", (1, True, "swap_12_34_blocked")),
        ("cS-S", "c-Sc", (1, True, "swap_12_34_blocked")),
        ("cSP-", "S-Sc", (1, True, "swap_12_34_blocked")),
        ("cSSS", "--SP", (1, True, "swap_14_23_blocked")),
        ("cSSS", "--SS", (1, True, "swap_14_23_blocked")),
    }
)
BASIC_HYBRID_MISS_ONLY_TOP_PEN_REMS: frozenset[tuple[str, str, tuple[int, bool, str | None]]] = frozenset(
    {
        ("cS-S", "--Sc", (1, True, None)),
        ("cS-S", "-cS-", (1, True, None)),
        ("cS--", "S-SS", (1, True, "swap_12_34_blocked")),
        ("cS-S", "S-Sc", (1, True, "swap_12_34_blocked")),
        ("cS--", "S--S", (1, True, "swap_12_34_blocked")),
        ("cS-S", "-P--", (1, True, None)),
        ("cS-S", "-S--", (1, True, None)),
        ("cS-S", "---P", (1, True, None)),
        ("cS-S", "---S", (1, True, None)),
        ("cS-S", "S-SS", (1, True, "swap_12_34_blocked")),
        ("cS-S", "S--S", (1, True, "swap_12_34_blocked")),
        ("cS--", "c--S", (1, True, "swap_12_34_blocked")),
        ("cS--", "c-Sc", (1, True, "swap_12_34_blocked")),
        ("cSSS", "--SP", (1, True, "swap_14_23_blocked")),
        ("cSSS", "--SS", (1, True, "swap_14_23_blocked")),
    }
)
REFERENCE_CPCP_DIR = PROJECT_ROOT / "reference_projects" / "shapez2-cpcp1998"


def load_corner_engine():
    spec = importlib.util.spec_from_file_location("corner_rule_main_for_symbolic", CORNER_MAIN)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["corner_rule_main_for_symbolic"] = mod
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.RuleEngine(mod.DEFAULT_RULE_SPECS)


CORNER_ENGINE = load_corner_engine()


@lru_cache(maxsize=200_000)
def corner_columns_allowed(code: str) -> bool:
    normalized = normalize_code(code)
    if not normalized:
        return True
    layers = normalized.split(":")
    for q in range(4):
        state = CORNER_ENGINE.start_state()
        for layer in layers:
            state = CORNER_ENGINE.step(state, layer[q])
            if state is None:
                return False
    return True


@lru_cache(maxsize=200_000)
def cached_skip_shape_analysis(shape_text: str) -> tuple[str, str]:
    from shape_classifier import analyze_shape

    return analyze_shape(shape_text, skip=True)


def _mask_for(layer: str, ch: str) -> int:
    mask = 0
    for i, c in enumerate(layer):
        if c == ch:
            mask |= 1 << i
    return mask


def _nonempty_mask(layer: str) -> int:
    mask = 0
    for i, c in enumerate(layer):
        if c != "-":
            mask |= 1 << i
    return mask


def _rotate_mask(mask: int, turns: int) -> int:
    out = 0
    for q in range(4):
        if mask & (1 << q):
            out |= 1 << ((q + turns) % 4)
    return out


def _rotate_tuple(values: tuple[int, int, int, int], turns: int) -> tuple[int, int, int, int]:
    out = [0, 0, 0, 0]
    for q, value in enumerate(values):
        out[(q + turns) % 4] = value
    return tuple(out)  # type: ignore[return-value]


def _rotate_bool_tuple(values: tuple[bool, bool, bool, bool], turns: int) -> tuple[bool, bool, bool, bool]:
    out = [False, False, False, False]
    for q, value in enumerate(values):
        out[(q + turns) % 4] = value
    return tuple(out)  # type: ignore[return-value]


def _rotate_cut_stable(values: tuple[bool, bool, bool, bool], turns: int) -> tuple[bool, bool, bool, bool]:
    # Order: west, east, north, south.
    out = values
    for _ in range(turns % 4):
        west, east, north, south = out
        out = (south, north, west, east)
    return out


def _layer_from_class(layer_class: tuple[int, int, int, int]) -> str:
    _nonempty, p_mask, s_mask, c_mask = layer_class
    chars = []
    for q in range(4):
        bit = 1 << q
        if c_mask & bit:
            chars.append("c")
        elif p_mask & bit:
            chars.append("P")
        elif s_mask & bit:
            chars.append("S")
        else:
            chars.append("-")
    return "".join(chars)


def _s_components(mask: int) -> tuple[int, ...]:
    components: list[int] = []
    unseen = mask
    while unseen:
        start = unseen & -unseen
        group = 0
        stack = [start.bit_length() - 1]
        while stack:
            q = stack.pop()
            bit = 1 << q
            if not (unseen & bit):
                continue
            unseen &= ~bit
            group |= bit
            for nq in ((q + 1) % 4, (q - 1) % 4):
                nbit = 1 << nq
                if unseen & nbit:
                    stack.append(nq)
        components.append(group)
    return tuple(components)


def _layer_has_no_c_support(prev_nonempty: int, p_mask: int, s_mask: int) -> bool:
    if p_mask & ~prev_nonempty:
        return False
    return all(component & prev_nonempty for component in _s_components(s_mask))


def _layer_has_side_support(prev_nonempty: int, p_mask: int, s_mask: int, c_mask: int, side_mask: int) -> bool:
    side_prev = prev_nonempty & side_mask
    if (p_mask | c_mask) & side_mask & ~side_prev:
        return False
    return all(component & side_prev for component in _s_components(s_mask & side_mask))


def _decode_column(code: int, depth: int) -> str:
    chars = []
    for _ in range(depth):
        chars.append(CODE_TO_SYMBOL[code & 3])
        code //= 4
    return "".join(reversed(chars))


def _canonical_c_components(
    labels: tuple[int, int, int, int],
    supported: tuple[bool, ...],
) -> tuple[tuple[int, int, int, int], tuple[bool, ...]]:
    mapping: dict[int, int] = {}
    next_label = 0
    out: list[int] = []
    out_supported: list[bool] = []
    for label in labels:
        if label < 0:
            out.append(-1)
            continue
        if label not in mapping:
            mapping[label] = next_label
            out_supported.append(bool(supported[label]))
            next_label += 1
        out.append(mapping[label])
    return tuple(out), tuple(out_supported)  # type: ignore[return-value]


class _UnionFind:
    def __init__(self) -> None:
        self.parent: list[int] = []
        self.supported: list[bool] = []

    def add(self, supported: bool) -> int:
        idx = len(self.parent)
        self.parent.append(idx)
        self.supported.append(supported)
        return idx

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> int:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return ra
        if rb < ra:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.supported[ra] = self.supported[ra] or self.supported[rb]
        return ra


LAYER_CLASSES = tuple(
    sorted(
        {
            (_nonempty_mask(layer), _mask_for(layer, "P"), _mask_for(layer, "S"), _mask_for(layer, "c"))
            for layer in LAYERS
        }
    )
)
LAYER_CLASS_TO_LAYER = {layer_class: _layer_from_class(layer_class) for layer_class in LAYER_CLASSES}


def _column_to_shape(column: str, q: int) -> str:
    layers = []
    for ch in column:
        chars = ["-", "-", "-", "-"]
        chars[q] = ch
        layers.append("".join(chars))
    return ":".join(layers)


@dataclass(frozen=True)
class SymbolicState:
    depth: int = field(compare=False)
    depth_bucket: int
    occupied_seen: bool
    c_seen: bool
    bottom_p_count: int
    bottom_s_count: int
    bottom_has_c: bool
    no_c_supported: bool
    highest_c_q: int
    highest_c_mask: int
    highest_c_layer_nonempty_mask: int
    corner_state_ids: tuple[int, int, int, int]
    opposite_col_kind: tuple[int, int, int, int]
    column_codes: tuple[int, int, int, int]
    column_nonempty_seen: tuple[bool, bool, bool, bool]
    column_s_seen: tuple[bool, bool, bool, bool]
    single_column_q: int
    single_column_code: int
    c_component_labels: tuple[int, int, int, int]
    c_component_supported: tuple[bool, ...]
    c_closed_unsupported: bool
    sorted_opposite_single_c_seen: tuple[bool, bool, bool, bool]
    cut_stable_sides: tuple[bool, bool, bool, bool]
    any_layer_c_with_three_s: bool
    prev_s_mask: int
    prev_c_mask: int
    top_s_mask: int
    top_nonempty_mask: int
    top_c_mask: int


@dataclass(frozen=True)
class ReferenceSwapWitness:
    angle: int
    left_half_bits: int
    right_half_bits: int


@dataclass(frozen=True)
class StackabilityWitness:
    base: str
    stacked_delta: str
    heights: tuple[int, int, int, int]
    base_swap: ReferenceSwapWitness | None


@dataclass(frozen=True)
class PpMinimalWitness:
    predecessor: str
    push_matches_target: bool
    predecessor_reference: tuple[str, str] | None
    predecessor_stackability: tuple[str, str] | None
    target_stackable_base_count: int


@dataclass(frozen=True)
class PpSubtypeWitness:
    subtype: str
    minimal: PpMinimalWitness
    bottom_pin_base: str | None
    derivative_base: str | None


@dataclass(frozen=True)
class DecompositionNode:
    kind: str
    shape: str
    detail: str
    children: tuple["DecompositionNode", ...] = ()


def decomposition_tree_root_key(node: DecompositionNode) -> str:
    return f"{normalize_code_label(node.kind)}:{normalize_code_label(node.detail)}"


def decomposition_tree_dependency_tags(node: DecompositionNode) -> tuple[str, ...]:
    tags: set[str] = set()

    def visit(current: DecompositionNode) -> None:
        detail = current.detail.lower()
        kind = current.kind.lower()
        if "hybrid" in detail or "hybrid" in kind:
            tags.add("hybrid")
        if "claw" in detail or "claw" in kind:
            tags.add("claw")
        if "pp" in detail or "pin" in detail:
            tags.add("pp")
        if "stack" in detail or "stack" in kind:
            tags.add("stack")
        if "swap" in detail or "swap" in kind:
            tags.add("swap")
        for child in current.children:
            visit(child)

    visit(node)
    return tuple(sorted(tags))


OPEN_DECOMPOSITION_LEAF_KINDS = frozenset(
    {
        "claw_predecessor",
        "hybrid_left",
        "hybrid_right",
        "pin_predecessor",
        "stack_input",
        "verified_predecessor",
    }
)


def decomposition_tree_open_leaf_keys(node: DecompositionNode) -> Counter[str]:
    leaves: Counter[str] = Counter()

    def visit(current: DecompositionNode) -> None:
        if current.children:
            for child in current.children:
                visit(child)
            return
        if current.kind in OPEN_DECOMPOSITION_LEAF_KINDS:
            leaves[decomposition_tree_root_key(current)] += 1
        elif current.kind == "pp" and current.detail == "empty_trace":
            leaves[decomposition_tree_root_key(current)] += 1

    visit(node)
    return leaves


@dataclass(frozen=True)
class HybridRescueWitness:
    mode: str
    left: str
    right: str


class FiniteHorizonCornerQuotient:
    def __init__(self, engine: object, max_depth: int) -> None:
        self.engine = engine
        self.max_depth = max_depth
        self.start_state = engine.start_state()
        self.raw_states = self._discover_raw_states()
        self.raw_transition: dict[tuple[object, str], object | None] = {}
        for state in self.raw_states:
            for ch in ALPHABET:
                self.raw_transition[(state, ch)] = engine.step(state, ch)
        self.class_by_remaining: list[dict[object, int]] = []
        self.representative_by_remaining: list[dict[int, object]] = []
        self.class_transition: dict[tuple[int, int, str], int | None] = {}
        self._build_classes()

    def _discover_raw_states(self) -> set[object]:
        seen = {self.start_state}
        frontier = {self.start_state}
        while frontier:
            next_frontier = set()
            for state in frontier:
                for ch in ALPHABET:
                    ns = self.engine.step(state, ch)
                    if ns is not None and ns not in seen:
                        seen.add(ns)
                        next_frontier.add(ns)
            frontier = next_frontier
        return seen

    def _build_classes(self) -> None:
        zero = {state: 0 for state in self.raw_states}
        self.class_by_remaining.append(zero)
        self.representative_by_remaining.append({0: next(iter(self.raw_states))})
        for remaining in range(1, self.max_depth + 1):
            previous = self.class_by_remaining[remaining - 1]
            sig_to_id: dict[tuple[int | None, ...], int] = {}
            classes: dict[object, int] = {}
            representatives: dict[int, object] = {}
            for state in self.raw_states:
                sig = tuple(
                    None if self.raw_transition[(state, ch)] is None else previous[self.raw_transition[(state, ch)]]
                    for ch in ALPHABET
                )
                if sig not in sig_to_id:
                    sig_to_id[sig] = len(sig_to_id)
                    representatives[sig_to_id[sig]] = state
                classes[state] = sig_to_id[sig]
            self.class_by_remaining.append(classes)
            self.representative_by_remaining.append(representatives)
            for class_id, representative in representatives.items():
                for ch in ALPHABET:
                    ns = self.raw_transition[(representative, ch)]
                    self.class_transition[(remaining, class_id, ch)] = None if ns is None else previous[ns]

    def start_class(self) -> int:
        return self.class_by_remaining[self.max_depth][self.start_state]

    def step_class(self, remaining: int, class_id: int, ch: str) -> int | None:
        if remaining <= 0:
            return class_id
        return self.class_transition[(remaining, class_id, ch)]

    def class_counts(self) -> list[int]:
        return [len(classes) for classes in self.class_by_remaining]


class SymbolicFrontierAutomaton:
    def __init__(
        self,
        corner_mode: str = "none",
        max_depth: int = 5,
        rotate_canonical: bool = False,
        experiments: frozenset[str] = frozenset(),
    ) -> None:
        self.corner_mode = corner_mode
        self.max_depth = max_depth
        self.rotate_canonical = rotate_canonical
        self.experiments = experiments
        self.corner_engine = load_corner_engine()
        self.single_column_verdicts: dict[tuple[int, str], str] = {}
        self._step_cache: dict[tuple[SymbolicState, tuple[int, int, int, int]], tuple[SymbolicState | None, str]] = {}
        self._corner_state_ids: dict[object, int] = {}
        self._corner_states: list[object] = []
        self.corner_quotient = (
            FiniteHorizonCornerQuotient(self.corner_engine, max_depth) if corner_mode == "quotient" else None
        )
        if corner_mode == "raw":
            start_corner_id = self._corner_id(self.corner_engine.start_state())
        elif corner_mode == "quotient":
            start_corner_id = self.corner_quotient.start_class()  # type: ignore[union-attr]
        else:
            start_corner_id = -1
        self.start = SymbolicState(
            depth=0,
            depth_bucket=0,
            occupied_seen=False,
            c_seen=False,
            bottom_p_count=0,
            bottom_s_count=0,
            bottom_has_c=False,
            no_c_supported=True,
            highest_c_q=-1,
            highest_c_mask=0,
            highest_c_layer_nonempty_mask=0,
            corner_state_ids=(start_corner_id, start_corner_id, start_corner_id, start_corner_id),
            opposite_col_kind=(0, 0, 0, 0),
            column_codes=(0, 0, 0, 0),
            column_nonempty_seen=(False, False, False, False),
            column_s_seen=(False, False, False, False),
            single_column_q=-1,
            single_column_code=0,
            c_component_labels=(-1, -1, -1, -1),
            c_component_supported=(),
            c_closed_unsupported=False,
            sorted_opposite_single_c_seen=(False, False, False, False),
            cut_stable_sides=(True, True, True, True),
            any_layer_c_with_three_s=False,
            prev_s_mask=0,
            prev_c_mask=0,
            top_s_mask=0,
            top_nonempty_mask=0,
            top_c_mask=0,
        )

    def _corner_id(self, state: object) -> int:
        if state not in self._corner_state_ids:
            self._corner_state_ids[state] = len(self._corner_states)
            self._corner_states.append(state)
        return self._corner_state_ids[state]

    def _corner_obj(self, state_id: int) -> object:
        return self._corner_states[state_id]

    def single_column_verdict(self, q: int, column: str) -> str:
        key = (q, column)
        if key not in self.single_column_verdicts:
            code = _column_to_shape(column, q)
            _legacy, strict, _cls, _reason = legacy_verdict(code)
            self.single_column_verdicts[key] = strict if strict in {"possible", "impossible"} else "unknown"
        return self.single_column_verdicts[key]

    def canonicalize(self, state: SymbolicState) -> SymbolicState:
        if not self.rotate_canonical:
            return state
        variants = []
        for turns in range(4):
            highest_c_q = -1 if state.highest_c_q < 0 else (state.highest_c_q + turns) % 4
            c_labels, c_supported = _canonical_c_components(
                _rotate_tuple(state.c_component_labels, turns),
                state.c_component_supported,
            )
            variants.append(
                SymbolicState(
                    depth=state.depth,
                    depth_bucket=state.depth_bucket,
                    occupied_seen=state.occupied_seen,
                    c_seen=state.c_seen,
                    bottom_p_count=state.bottom_p_count,
                    bottom_s_count=state.bottom_s_count,
                    bottom_has_c=state.bottom_has_c,
                    no_c_supported=state.no_c_supported,
                    highest_c_q=highest_c_q,
                    highest_c_mask=_rotate_mask(state.highest_c_mask, turns),
                    highest_c_layer_nonempty_mask=_rotate_mask(state.highest_c_layer_nonempty_mask, turns),
                    corner_state_ids=_rotate_tuple(state.corner_state_ids, turns),
                    opposite_col_kind=_rotate_tuple(state.opposite_col_kind, turns),
                    column_codes=_rotate_tuple(state.column_codes, turns),
                    column_nonempty_seen=_rotate_bool_tuple(state.column_nonempty_seen, turns),
                    column_s_seen=_rotate_bool_tuple(state.column_s_seen, turns),
                    single_column_q=-2 if state.single_column_q == -2 else -1 if state.single_column_q == -1 else (state.single_column_q + turns) % 4,
                    single_column_code=state.single_column_code,
                    c_component_labels=c_labels,
                    c_component_supported=c_supported,
                    c_closed_unsupported=state.c_closed_unsupported,
                    sorted_opposite_single_c_seen=_rotate_bool_tuple(state.sorted_opposite_single_c_seen, turns),
                    cut_stable_sides=_rotate_cut_stable(state.cut_stable_sides, turns),
                    any_layer_c_with_three_s=state.any_layer_c_with_three_s,
                    prev_s_mask=_rotate_mask(state.prev_s_mask, turns),
                    prev_c_mask=_rotate_mask(state.prev_c_mask, turns),
                    top_s_mask=_rotate_mask(state.top_s_mask, turns),
                    top_nonempty_mask=_rotate_mask(state.top_nonempty_mask, turns),
                    top_c_mask=_rotate_mask(state.top_c_mask, turns),
                )
            )
        return min(variants, key=lambda s: (
            s.depth_bucket,
            s.occupied_seen,
            s.c_seen,
            s.bottom_p_count,
            s.bottom_s_count,
            s.bottom_has_c,
            s.no_c_supported,
            s.highest_c_q,
            s.highest_c_mask,
            s.highest_c_layer_nonempty_mask,
            s.corner_state_ids,
            s.opposite_col_kind,
            s.column_codes,
            s.column_nonempty_seen,
            s.column_s_seen,
            s.single_column_q,
            s.single_column_code,
            s.c_component_labels,
            s.c_component_supported,
            s.c_closed_unsupported,
            s.sorted_opposite_single_c_seen,
            s.cut_stable_sides,
            s.any_layer_c_with_three_s,
            s.prev_s_mask,
            s.prev_c_mask,
            s.top_s_mask,
            s.top_nonempty_mask,
            s.top_c_mask,
        ))

    def step_class(self, state: SymbolicState, layer_class: tuple[int, int, int, int]) -> tuple[SymbolicState | None, str]:
        key = (state, layer_class)
        if key in self._step_cache:
            return self._step_cache[key]

        depth = state.depth + 1
        depth_bucket = min(depth, 4)
        nonempty, p_mask, s_mask, c_mask = layer_class
        layer = LAYER_CLASS_TO_LAYER[layer_class]

        next_corner_ids = list(state.corner_state_ids)
        if self.corner_mode == "raw":
            next_corner_ids = []
            for state_id, ch in zip(state.corner_state_ids, layer):
                ns = self.corner_engine.step(self._corner_obj(state_id), ch)
                if ns is None:
                    self._step_cache[key] = (None, "corner_forbidden")
                    return self._step_cache[key]
                next_corner_ids.append(self._corner_id(ns))
        elif self.corner_mode == "quotient":
            next_corner_ids = []
            remaining = self.max_depth - state.depth
            for class_id, ch in zip(state.corner_state_ids, layer):
                ns = self.corner_quotient.step_class(remaining, class_id, ch)  # type: ignore[union-attr]
                if ns is None:
                    self._step_cache[key] = (None, "corner_forbidden")
                    return self._step_cache[key]
                next_corner_ids.append(ns)

        bottom_p_count = state.bottom_p_count
        bottom_s_count = state.bottom_s_count
        bottom_has_c = state.bottom_has_c
        if state.depth == 0:
            bottom_p_count = bin(p_mask).count("1")
            bottom_s_count = bin(s_mask).count("1")
            bottom_has_c = bool(c_mask)

        no_c_supported = state.no_c_supported
        if state.depth > 0 and not _layer_has_no_c_support(state.top_nonempty_mask, p_mask, s_mask):
            no_c_supported = False

        side_masks = (0b1100, 0b0011, 0b1001, 0b0110)
        cut_stable_sides = list(state.cut_stable_sides)
        if state.depth > 0:
            for i, side_mask in enumerate(side_masks):
                if cut_stable_sides[i] and not _layer_has_side_support(
                    state.top_nonempty_mask, p_mask, s_mask, c_mask, side_mask
                ):
                    cut_stable_sides[i] = False

        highest_c_q = state.highest_c_q
        highest_c_mask = state.highest_c_mask
        highest_c_layer_nonempty_mask = state.highest_c_layer_nonempty_mask
        if c_mask:
            highest_c_q = min(i for i in range(4) if c_mask & (1 << i))
            highest_c_mask = c_mask
            highest_c_layer_nonempty_mask = nonempty
        any_layer_c_with_three_s = state.any_layer_c_with_three_s or (bool(c_mask) and bin(s_mask).count("1") >= 3)

        uf = _UnionFind()
        old_to_node: dict[int, int] = {}
        for old_label, is_supported in enumerate(state.c_component_supported):
            old_to_node[old_label] = uf.add(is_supported)
        new_nodes: dict[int, int] = {}
        carried_old_labels: set[int] = set()
        for q in range(4):
            bit = 1 << q
            if not (c_mask & bit):
                continue
            node = uf.add(state.depth == 0 or bool(state.top_nonempty_mask & bit))
            old_label = state.c_component_labels[q]
            if old_label >= 0:
                carried_old_labels.add(old_label)
                node = uf.union(node, old_to_node[old_label])
            new_nodes[q] = node
        for q in range(4):
            if q in new_nodes and (q + 1) % 4 in new_nodes:
                uf.union(new_nodes[q], new_nodes[(q + 1) % 4])

        closed_unsupported = state.c_closed_unsupported
        for old_label, is_supported in enumerate(state.c_component_supported):
            if old_label not in carried_old_labels and not is_supported:
                closed_unsupported = True

        raw_c_labels = [-1, -1, -1, -1]
        root_supported: dict[int, bool] = {}
        for q, node in new_nodes.items():
            root = uf.find(node)
            raw_c_labels[q] = root
            root_supported[root] = root_supported.get(root, False) or uf.supported[uf.find(root)]
        root_to_index = {root: idx for idx, root in enumerate(sorted(root_supported))}
        c_labels = tuple(root_to_index[label] if label >= 0 else -1 for label in raw_c_labels)
        c_supported = tuple(root_supported[root] for root in sorted(root_supported))

        opposite_col = list(state.opposite_col_kind)
        column_codes = list(state.column_codes)
        column_nonempty_seen = list(state.column_nonempty_seen)
        column_s_seen = list(state.column_s_seen)
        for q in range(4):
            if nonempty & (1 << q):
                column_nonempty_seen[q] = True
            if s_mask & (1 << q):
                column_s_seen[q] = True
        single_column_q = state.single_column_q
        single_column_code = state.single_column_code
        layer_nonempty_count = bin(nonempty).count("1")
        if single_column_q != -2:
            if not state.occupied_seen:
                if layer_nonempty_count == 0:
                    single_column_q = -1
                    single_column_code = single_column_code * 4
                elif layer_nonempty_count == 1:
                    single_column_q = (nonempty & -nonempty).bit_length() - 1
                    single_column_code = single_column_code * 4 + SYMBOL_TO_CODE[layer[single_column_q]]
                else:
                    single_column_q = -2
                    single_column_code = 0
            elif single_column_q >= 0:
                if nonempty & ~(1 << single_column_q):
                    single_column_q = -2
                    single_column_code = 0
                else:
                    single_column_code = single_column_code * 4 + SYMBOL_TO_CODE[layer[single_column_q]]
        if self.experiments & {"split-opposite", "promote-empty-opposite", "promote-dead-opposite-tail"}:
            for q, ch in enumerate(layer):
                column_codes[q] = column_codes[q] * 4 + SYMBOL_TO_CODE[ch]
        if highest_c_q != -1:
            for q in range(4):
                bit = 1 << q
                ch = "c" if c_mask & bit else "P" if p_mask & bit else "S" if s_mask & bit else "-"
                old = opposite_col[q]
                if old == 3:
                    continue
                if ch == "c":
                    opposite_col[q] = 3
                elif ch in ("P", "S"):
                    opposite_col[q] = max(old, 1)
        sorted_opposite_single_c_seen = list(state.sorted_opposite_single_c_seen)
        for candidate_hq in range(4):
            opposite_bit = 1 << ((candidate_hq + 2) % 4)
            if nonempty == opposite_bit and c_mask == opposite_bit:
                sorted_opposite_single_c_seen[candidate_hq] = True

        next_state = self.canonicalize(
            SymbolicState(
                depth=depth,
                depth_bucket=depth_bucket,
                occupied_seen=state.occupied_seen or bool(nonempty),
                c_seen=state.c_seen or bool(c_mask),
                bottom_p_count=bottom_p_count,
                bottom_s_count=bottom_s_count,
                bottom_has_c=bottom_has_c,
                no_c_supported=no_c_supported,
                highest_c_q=highest_c_q,
                highest_c_mask=highest_c_mask,
                highest_c_layer_nonempty_mask=highest_c_layer_nonempty_mask,
                corner_state_ids=tuple(next_corner_ids),  # type: ignore[arg-type]
                opposite_col_kind=tuple(opposite_col),  # type: ignore[arg-type]
                column_codes=tuple(column_codes),  # type: ignore[arg-type]
                column_nonempty_seen=tuple(column_nonempty_seen),  # type: ignore[arg-type]
                column_s_seen=tuple(column_s_seen),  # type: ignore[arg-type]
                single_column_q=single_column_q,
                single_column_code=single_column_code,
                c_component_labels=c_labels,  # type: ignore[arg-type]
                c_component_supported=c_supported,
                c_closed_unsupported=closed_unsupported,
                sorted_opposite_single_c_seen=tuple(sorted_opposite_single_c_seen),  # type: ignore[arg-type]
                cut_stable_sides=tuple(cut_stable_sides),  # type: ignore[arg-type]
                any_layer_c_with_three_s=any_layer_c_with_three_s,
                prev_s_mask=state.top_s_mask,
                prev_c_mask=state.top_c_mask,
                top_s_mask=s_mask,
                top_nonempty_mask=nonempty,
                top_c_mask=c_mask,
            )
        )
        self._step_cache[key] = (next_state, "ok")
        return self._step_cache[key]

    def step(self, state: SymbolicState, layer: str) -> tuple[SymbolicState | None, str]:
        return self.step_class(
            state,
            (_nonempty_mask(layer), _mask_for(layer, "P"), _mask_for(layer, "S"), _mask_for(layer, "c")),
        )

    def terminal_bucket(self, state: SymbolicState) -> str:
        def unknown(name: str) -> str:
            if "split-cut" not in self.experiments:
                return name
            west_stable, east_stable, north_stable, south_stable = state.cut_stable_sides
            vertical_swapable = west_stable and east_stable
            horizontal_swapable = north_stable and south_stable
            multi_quadrant_seen = sum(1 for seen in state.column_nonempty_seen if seen) >= 2
            return f"{name}_cutV{int(vertical_swapable)}H{int(horizontal_swapable)}M{int(multi_quadrant_seen)}"

        unsupported_c_count = sum(1 for supported in state.c_component_supported if not supported)

        if not state.occupied_seen:
            return "possible_empty"
        if state.single_column_q >= 0:
            column = _decode_column(state.single_column_code, state.depth)
            verdict = self.single_column_verdict(state.single_column_q, column)
            if verdict == "possible":
                return "possible_single_column_corner"
            if verdict == "impossible":
                return "impossible_single_column_corner"
        if not state.c_seen:
            if state.depth <= 1 or state.no_c_supported:
                return "possible_supported_no_c"
            if "promote-no-c" in self.experiments:
                return "possible_experiment_no_c"
            return "impossible_no_c_unsupported"
        if state.c_closed_unsupported:
            if "promote-closed-c" in self.experiments:
                return "impossible_experiment_closed_c_component"
            return unknown("unknown_closed_c_component_candidate")

        west_stable, east_stable, north_stable, south_stable = state.cut_stable_sides
        vertical_swapable = west_stable and east_stable
        horizontal_swapable = north_stable and south_stable
        multi_quadrant_seen = sum(1 for seen in state.column_nonempty_seen if seen) >= 2
        if multi_quadrant_seen and (vertical_swapable or horizontal_swapable):
            return "possible_cut_swapable"
        if state.highest_c_q >= 0 and state.sorted_opposite_single_c_seen[state.highest_c_q]:
            return "impossible_sorted_opposite_single_c_layer"

        if state.bottom_p_count <= 1:
            if "promote-claw-bottom" in self.experiments:
                return "impossible_experiment_claw_pin_count"
            if sum(1 for seen in state.column_nonempty_seen if seen) == 2:
                return "impossible_claw_pin_two_columns"
            if state.depth == 2:
                return "possible_depth2_claw_pin"
            if unsupported_c_count == 1 and state.top_s_mask == 0:
                return "impossible_open_c_without_top_s"
            return unknown("unknown_claw_pin_count_candidate")
        if state.bottom_has_c:
            if "promote-claw-bottom" in self.experiments:
                return "impossible_experiment_bottom_c"
            if unsupported_c_count == 1 and state.top_s_mask == 0:
                return "impossible_bottom_c_open_c_without_top_s"
            return unknown("unknown_bottom_c_candidate")
        if state.bottom_s_count >= 2:
            if "promote-claw-bottom" in self.experiments:
                return "impossible_experiment_bottom_s_count"
            return unknown("unknown_bottom_s_count_candidate")

        if state.highest_c_q != -1:
            opp_q = (state.highest_c_q + 2) % 4
            if (
                state.top_c_mask == state.highest_c_mask
                and bin(state.highest_c_mask).count("1") == 1
                and bin(state.highest_c_layer_nonempty_mask).count("1") == 1
                and not state.column_nonempty_seen[opp_q]
            ):
                return "impossible_empty_opposite_column"
            if state.opposite_col_kind[opp_q] in (0, 3):
                if "promote-top-three-s" in self.experiments and bin(state.top_nonempty_mask & ~state.top_c_mask).count("1") >= 3:
                    return "possible_experiment_top_three_s_witness"
                if state.any_layer_c_with_three_s:
                    return unknown("unknown_opposite_bridge_witness_candidate")
                if sum(1 for seen in state.column_nonempty_seen if seen) == 2:
                    return "impossible_scaffold_two_columns"
                if (
                    "promote-scaffold-pppp-no-opp-s" in self.experiments
                    and state.bottom_p_count == 4
                    and not state.column_s_seen[opp_q]
                ):
                    return "possible_experiment_scaffold_pppp_no_opposite_s"
                if "promote-dead-opposite-tail" in self.experiments:
                    col = _decode_column(state.column_codes[opp_q], state.depth)
                    if len(col) >= 5 and col[0] == "P" and "c" in col[:-2] and col[-2:] == "--":
                        return "impossible_experiment_dead_opposite_tail"
                if "promote-empty-opposite" in self.experiments:
                    col = _decode_column(state.column_codes[opp_q], state.depth)
                    if col and set(col) == {"-"}:
                        return "impossible_experiment_empty_opposite_column"
                if "promote-opposite" in self.experiments:
                    return "impossible_experiment_opposite_scaffold"
                if "split-opposite" in self.experiments:
                    col = _decode_column(state.column_codes[opp_q], state.depth)
                    return "unknown_opposite_col_" + col
                return unknown("unknown_opposite_scaffold_candidate")

        if state.top_nonempty_mask == state.top_c_mask and state.top_c_mask in (1, 2, 4, 8):
            if "promote-top-single-c" in self.experiments:
                return "impossible_experiment_top_single_c"
            if sum(1 for seen in state.column_nonempty_seen if seen) == 2:
                return "impossible_top_single_c_two_columns"
            return unknown("unknown_top_single_c_candidate")
        if state.bottom_p_count == 4:
            if "promote-full-pin" in self.experiments:
                return "possible_experiment_full_pin_bottom_claw"
            return unknown("unknown_full_pin_bottom_claw_candidate")
        if sum(1 for seen in state.column_nonempty_seen if seen) == 2:
            return "impossible_claw_frontier_two_columns"
        return unknown("unknown_claw_frontier")

    def is_absorbing_bucket(self, bucket: str, frontier_cutoff: bool = False) -> bool:
        if bucket.startswith("impossible_"):
            return True
        if frontier_cutoff and bucket.startswith("unknown_"):
            return True
        return False

    def build_reachable(
        self,
        max_depth: int,
        max_states: int = 0,
        max_seconds: float = 0.0,
        progress_every: int = 0,
        collect_bucket_edges: bool = False,
        frontier_cutoff: bool = False,
    ) -> tuple[list[SymbolicState], int, int, bool, Counter[tuple[str, str]]]:
        started = time.perf_counter()
        ids = {self.start: 0}
        states = [self.start]
        edge_count = 0
        dead_edges = 0
        bucket_edges: Counter[tuple[str, str]] = Counter()
        queue = deque([self.start])
        expanded = 0
        truncated = False
        while queue:
            if max_seconds > 0 and time.perf_counter() - started > max_seconds:
                truncated = True
                break
            state = queue.popleft()
            if state.depth >= max_depth:
                continue
            if self.is_absorbing_bucket(self.terminal_bucket(state), frontier_cutoff):
                continue
            expanded += 1
            if progress_every and expanded % progress_every == 0:
                print(f"progress expanded={expanded} states={len(states)} edges={edge_count}")
            for layer_class in LAYER_CLASSES:
                ns, reason = self.step_class(state, layer_class)
                edge_count += 1
                if ns is None:
                    dead_edges += 1
                    if collect_bucket_edges:
                        bucket_edges[(self.terminal_bucket(state), reason)] += 1
                    continue
                if collect_bucket_edges:
                    bucket_edges[(self.terminal_bucket(state), self.terminal_bucket(ns))] += 1
                if ns not in ids:
                    ids[ns] = len(states)
                    states.append(ns)
                    queue.append(ns)
                    if max_states and len(states) >= max_states:
                        truncated = True
                        return states, edge_count, dead_edges, truncated, bucket_edges
        return states, edge_count, dead_edges, truncated, bucket_edges


def mermaid_summary(buckets: Counter[str]) -> str:
    lines = ["flowchart TD", '    Start["start"] --> Scan["scan layers with symbolic state"]']
    for bucket, count in buckets.most_common():
        lines.append(f'    Scan --> {bucket}["{bucket}<br/>{count} states"]')
    return "\n".join(lines)


def mermaid_bucket_graph(bucket_edges: Counter[tuple[str, str]]) -> str:
    lines = ["flowchart LR"]
    for (src, dst), count in bucket_edges.most_common(80):
        lines.append(f'    B_{src}["{src}"] -->|"{count}"| B_{dst}["{dst}"]')
    return "\n".join(lines)


def _mask_text(mask: int) -> str:
    return format(mask, "04b")


def state_quotient_label(state: SymbolicState, bucket: str) -> str:
    columns = sum(1 for seen in state.column_nonempty_seen if seen)
    c_components = len(state.c_component_supported)
    unsupported_c = sum(1 for supported in state.c_component_supported if not supported)
    highest = (
        "none"
        if state.highest_c_q < 0
        else "single"
        if bin(state.highest_c_mask).count("1") == 1
        else "multi"
    )
    bottom_p = min(state.bottom_p_count, 4)
    bottom_s = "2+" if state.bottom_s_count >= 2 else str(state.bottom_s_count)
    top_nonempty = bin(state.top_nonempty_mask).count("1")
    top_c = bin(state.top_c_mask).count("1")
    return (
        f"d{state.depth}"
        f"|{bucket}"
        f"|bp{bottom_p}s{bottom_s}c{int(state.bottom_has_c)}"
        f"|cols{columns}"
        f"|top{top_nonempty}c{top_c}"
        f"|hc{highest}"
        f"|cc{c_components}u{unsupported_c}"
    )


def _node_id(label: str) -> str:
    return "Q_" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:12]


def mermaid_automaton_graph(
    automaton: SymbolicFrontierAutomaton,
    states: list[SymbolicState],
    edge_limit: int = 120,
) -> str:
    state_set = set(states)
    node_counts: Counter[str] = Counter()
    edges: Counter[tuple[str, str]] = Counter()
    dead_edges: Counter[tuple[str, str]] = Counter()

    for state in states:
        src = state_quotient_label(state, automaton.terminal_bucket(state))
        node_counts[src] += 1
        if state.depth >= automaton.max_depth:
            continue
        if automaton.is_absorbing_bucket(automaton.terminal_bucket(state)):
            continue
        for layer_class in LAYER_CLASSES:
            ns, reason = automaton.step_class(state, layer_class)
            if ns is None:
                dead_edges[(src, reason)] += 1
                continue
            if ns not in state_set:
                continue
            dst = state_quotient_label(ns, automaton.terminal_bucket(ns))
            edges[(src, dst)] += 1

    lines = ["flowchart LR"]
    shown_nodes: set[str] = set()
    for (src, dst), count in edges.most_common(edge_limit):
        shown_nodes.add(src)
        shown_nodes.add(dst)
        lines.append(f'    {_node_id(src)}["{src}<br/>states={node_counts[src]}"] -->|"{count}"| {_node_id(dst)}["{dst}<br/>states={node_counts[dst]}"]')
    for (src, reason), count in dead_edges.most_common(max(10, edge_limit // 8)):
        shown_nodes.add(src)
        dead = f"dead:{reason}"
        lines.append(f'    {_node_id(src)}["{src}<br/>states={node_counts[src]}"] -->|"{count}"| {_node_id(dead)}["{dead}"]')
    if not shown_nodes:
        lines.append('    Empty["no visible transitions"]')
    return "\n".join(lines)


def mermaid_decision_graph() -> str:
    return """flowchart TD
    A["입력 도형"] --> B["아래층부터 frontier scan"]
    B --> C["corner quotient 전이"]
    C -->|금지 상태| X0["impossible: corner_forbidden"]
    C --> D["frontier 상태 갱신"]

    D --> D1["P/S 물리 지지<br/>no_c_supported"]
    D --> D2["c 연결성 frontier<br/>component labels + supported"]
    D --> D3["컬럼 이력<br/>nonempty / S / single-column"]
    D --> D4["highest-c 문맥<br/>q, mask, opposite column"]
    D --> D5["cut 안정성<br/>west/east/north/south"]
    D1 --> T["terminal decision"]
    D2 --> T
    D3 --> T
    D4 --> T
    D5 --> T

    T --> Q0{"occupied 없음?"}
    Q0 -->|yes| P0["possible_empty"]
    Q0 -->|no| Q1{"single column 유지?"}
    Q1 -->|yes| Q1a{"q별 1D quotient"}
    Q1a -->|possible| P1["possible_single_column_corner"]
    Q1a -->|impossible| X1["impossible_single_column_corner"]
    Q1a -->|unknown| Q2
    Q1 -->|no| Q2{"c 없음?"}

    Q2 -->|yes, supported| P2["possible_supported_no_c"]
    Q2 -->|yes, unsupported| X2["impossible_no_c_unsupported"]
    Q2 -->|no| Q3{"unsupported c component 닫힘?"}
    Q3 -->|yes| U1["unknown_closed_c_component_candidate"]
    Q3 -->|no| Q4{"stable cut 존재?"}

    Q4 -->|yes| P3["possible_cut_swapable"]
    Q4 -->|no| Q5{"bottom P <= 1?"}
    Q5 -->|yes, 2 columns| X3["impossible_claw_pin_two_columns"]
    Q5 -->|yes, otherwise| U2["unknown_claw_pin_count_candidate"]
    Q5 -->|no| Q6{"bottom에 c 있음?"}

    Q6 -->|yes| U3["unknown_bottom_c_candidate"]
    Q6 -->|no| Q7{"bottom S >= 2?"}
    Q7 -->|yes| U4["unknown_bottom_s_count_candidate"]
    Q7 -->|no| Q8{"highest c 있음?"}

    Q8 -->|yes| Q8a{"highest c가 단일이고<br/>opposite column 비어 있음?"}
    Q8a -->|yes| X4["impossible_empty_opposite_column"]
    Q8a -->|no| Q8b{"opposite scaffold/bridge 후보?"}
    Q8b -->|bridge + SS tail| P4["possible_bridge_opposite_ss_tail"]
    Q8b -->|scaffold + SS tail| P5["possible_scaffold_opposite_ss_tail"]
    Q8b -->|2 columns| X5["impossible_scaffold_two_columns"]
    Q8b -->|mixed| U5["unknown_opposite_scaffold_candidate"]
    Q8b -->|bridge mixed| U6["unknown_opposite_bridge_witness_candidate"]
    Q8 -->|no| Q9{"top single c?"}

    Q9 -->|yes| U7["unknown_top_single_c_candidate"]
    Q9 -->|no| Q10{"bottom P == 4?"}
    Q10 -->|yes, csss cap| P6["possible_fullpin_csss_cap"]
    Q10 -->|yes, mixed| U8["unknown_full_pin_bottom_claw_candidate"]
    Q10 -->|no| U9["unknown_claw_frontier"]"""


def normalize_layer(layer: str) -> str:
    chars = []
    for ch in layer[:4].ljust(4, "-"):
        chars.append("S" if ch in "CRW" else ch if ch in "SPc-" else "-")
    return "".join(chars)


def normalize_code(code: str) -> str:
    code = code.strip()
    if not code:
        return ""
    if ":" in code:
        layers = [normalize_layer(part) for part in code.split(":")]
    else:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                from data_operations import simplify_shape

                simplified = simplify_shape(code)
            layers = [normalize_layer(part) for part in simplified.split(":")]
        except Exception:
            layers = [normalize_layer(code)]
    while layers and layers[-1] == "----":
        layers.pop()
    return ":".join(layers)


def extract_codes(path: Path, max_layers: int = MAX_LAYERS) -> Iterable[str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        for token in re.split(r"\s+", line):
            token = token.strip().strip(",;")
            if not token or "=" in token or not TOKEN_RE.match(token):
                continue
            if any(ch in token for ch in "SPcCRW:-"):
                try:
                    normalized = normalize_code(token)
                except Exception:
                    continue
                if normalized and len(normalized.split(":")) <= max_layers:
                    yield normalized


def iter_data_codes(data_dir: Path, max_layers: int = MAX_LAYERS) -> Iterable[str]:
    seen: set[str] = set()
    paths = [data_dir] if data_dir.is_file() else sorted(data_dir.rglob("*.txt"))
    for path in paths:
        for code in extract_codes(path, max_layers):
            if code not in seen:
                seen.add(code)
                yield code


def iter_data_codes_by_file(data_dir: Path, per_file: int, seed: int, shuffle: bool = True, max_layers: int = MAX_LAYERS) -> Iterable[str]:
    rng = random.Random(seed)
    seen: set[str] = set()
    sampled: list[str] = []
    paths = [data_dir] if data_dir.is_file() else sorted(data_dir.rglob("*.txt"))
    for path in paths:
        file_codes = []
        file_seen: set[str] = set()
        for code in extract_codes(path, max_layers):
            if code in file_seen:
                continue
            file_seen.add(code)
            file_codes.append(code)
        if shuffle:
            rng.shuffle(file_codes)
        take = file_codes if per_file <= 0 else file_codes[:per_file]
        for code in take:
            if code not in seen:
                seen.add(code)
                sampled.append(code)
    if shuffle:
        rng.shuffle(sampled)
    yield from sampled


def iter_random_codes(samples: int, layers: int, seed: int) -> Iterable[str]:
    rng = random.Random(seed)
    for _ in range(samples):
        yield ":".join("".join(rng.choice(ALPHABET) for _ in range(4)) for _ in range(layers))


def symbolic_verdict(automaton: SymbolicFrontierAutomaton, code: str, max_depth: int) -> tuple[str, str]:
    normalized = normalize_code(code)
    if not normalized:
        return "possible", "possible_empty"
    layers = normalized.split(":")
    if len(layers) > max_depth:
        return "unknown", "layers_exceeded"
    state = automaton.start
    for layer in layers:
        ns, reason = automaton.step(state, layer)
        if ns is None:
            return "impossible", reason
        state = ns
    bucket = automaton.terminal_bucket(state)
    if bucket.startswith("possible_"):
        return "possible", bucket
    if bucket.startswith("impossible_"):
        return "impossible", bucket
    return "unknown", bucket


def strict_legacy_parts_to_symbolic(strict: str, cls: str, reason: str) -> tuple[str, str]:
    if strict == "possible":
        return "possible", "fallback_legacy_core_" + normalize_code_label(cls or "possible")
    if strict == "impossible":
        return "impossible", "fallback_legacy_core_" + normalize_code_label(reason or cls or "impossible")
    return "unknown", "fallback_legacy_core_unknown"


def strict_legacy_verdict_to_symbolic(code: str) -> tuple[str, str]:
    _legacy, strict, cls, reason = legacy_verdict(code)
    return strict_legacy_parts_to_symbolic(strict, cls, reason)


def _adjacent_q(q: int) -> tuple[int, int]:
    return ((1, 3), (0, 2), (1, 3), (0, 2))[q]


def _cpcp_shape_bits(code: str, layers: int) -> int:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    while len(parts) < layers:
        parts.append("----")
    bits = 0
    # cpcp1998 dump encoding is Empty=0, Pin=1, Shape=2, Crystal=3.
    mapping = {"-": 0, "P": 1, "S": 2, "c": 3}
    for l, layer in enumerate(parts[:layers]):
        for q, ch in enumerate(layer):
            bits |= mapping.get(ch, 2) << (2 * (l * 4 + q))
    return bits


def _cpcp_rotate_bits(bits: int, layers: int, angle: int) -> int:
    out = 0
    for l in range(layers):
        for q in range(4):
            value = (bits >> (2 * (l * 4 + q))) & 3
            out |= value << (2 * (l * 4 + ((q - angle) % 4)))
    return out


def _cpcp_flip_bits(bits: int, layers: int) -> int:
    out = 0
    for l in range(layers):
        for q in range(4):
            value = (bits >> (2 * (l * 4 + q))) & 3
            out |= value << (2 * (l * 4 + (3 - q)))
    return out


def _cpcp_equiv_shape_min(bits: int, layers: int) -> int:
    variants = []
    for angle in range(4):
        rotated = _cpcp_rotate_bits(bits, layers, angle)
        variants.append(rotated)
        variants.append(_cpcp_flip_bits(rotated, layers))
    return min(variants)


def _cpcp_equiv_half_min(bits: int, layers: int) -> int:
    return min(bits, _cpcp_rotate_bits(_cpcp_flip_bits(bits, layers), layers, 2))


@lru_cache(maxsize=8)
def _load_cpcp_dump(layers: int) -> tuple[frozenset[int], frozenset[int]]:
    dump = REFERENCE_CPCP_DIR / f"dump{layers}.bin"
    if not dump.exists():
        return frozenset(), frozenset()
    data = dump.read_bytes()
    width = 4 if layers <= 4 else 8
    fmt = "<I" if width == 4 else "<Q"
    pos = 0
    half_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    halves = frozenset(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(half_count))
    pos += half_count * width
    shape_count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    shapes = frozenset(struct.unpack_from(fmt, data, pos + i * width)[0] for i in range(shape_count))
    return halves, shapes


@lru_cache(maxsize=100_000)
def reference_cpcp_swappable_verdict(code: str, layers: int) -> tuple[str, str] | None:
    witness = reference_cpcp_swappable_witness(code, layers)
    if witness is not None:
        return "possible", "reference_cpcp_swappable"
    return None


@lru_cache(maxsize=100_000)
def reference_cpcp_swappable_witness(code: str, layers: int) -> ReferenceSwapWitness | None:
    halves, shapes = _load_cpcp_dump(layers)
    if not halves:
        return None
    bits = _cpcp_shape_bits(code, layers)
    mask_half = 0
    for l in range(layers):
        for q in range(2):
            mask_half |= 3 << (2 * (l * 4 + q))
    for angle in range(2):
        rotated = _cpcp_rotate_bits(bits, layers, angle)
        left = _cpcp_equiv_half_min(rotated & mask_half, layers)
        right = _cpcp_equiv_half_min(_cpcp_rotate_bits(bits, layers, angle + 2) & mask_half, layers)
        if left in halves and right in halves:
            return ReferenceSwapWitness(angle=angle, left_half_bits=left, right_half_bits=right)
    return None


@lru_cache(maxsize=100_000)
def reference_cpcp_verdict(code: str, layers: int) -> tuple[str, str] | None:
    halves, shapes = _load_cpcp_dump(layers)
    if not halves and not shapes:
        return None
    swappable = reference_cpcp_swappable_verdict(code, layers)
    if swappable is not None:
        return swappable
    bits = _cpcp_shape_bits(code, layers)
    if _cpcp_equiv_shape_min(bits, layers) in shapes:
        return "possible", "reference_cpcp_non_swappable"
    return "impossible", "reference_cpcp_not_in_dump"


def _trim_layers(layers: list[list[str]]) -> list[list[str]]:
    while layers and all(ch == "-" for ch in layers[-1]):
        layers.pop()
    return layers


def _piece_at(layers: list[list[str]], l: int, q: int) -> str:
    if l < 0 or l >= len(layers):
        return "-"
    return layers[l][q]


def _connected_group(layers: list[list[str]], start_l: int, start_q: int) -> set[tuple[int, int]]:
    start = _piece_at(layers, start_l, start_q)
    if start == "-":
        return set()
    if start == "P":
        return {(start_l, start_q)}
    is_c = start == "c"
    queue = [(start_l, start_q)]
    seen: set[tuple[int, int]] = set()
    group: set[tuple[int, int]] = set()
    while queue:
        l, q = queue.pop(0)
        if (l, q) in seen:
            continue
        seen.add((l, q))
        if _piece_at(layers, l, q) == "-":
            continue
        group.add((l, q))
        for nq in _adjacent_q(q):
            ch = _piece_at(layers, l, nq)
            if (is_c and ch == "c") or (not is_c and ch not in ("-", "P", "c")):
                queue.append((l, nq))
        if is_c:
            for nl in (l - 1, l + 1):
                if _piece_at(layers, nl, q) == "c":
                    queue.append((nl, q))
    return group


def _shatter_set(layers: list[list[str]], initial: set[tuple[int, int]]) -> set[tuple[int, int]]:
    total = set(initial)
    queue = {coord for coord in initial if _piece_at(layers, *coord) == "c"}
    while queue:
        l, q = queue.pop()
        group = _connected_group(layers, l, q)
        newly = group - total
        if not newly:
            continue
        total.update(newly)
        for sl, sq in newly:
            for nl in (sl - 1, sl + 1):
                if _piece_at(layers, nl, sq) == "c" and (nl, sq) not in total:
                    queue.add((nl, sq))
            for nq in _adjacent_q(sq):
                if _piece_at(layers, sl, nq) == "c" and (sl, nq) not in total:
                    queue.add((sl, nq))
    return total


@lru_cache(maxsize=200_000)
def bitmask_apply_physics(code: str) -> str:
    normalized = normalize_code(code)
    layers = [list(layer) for layer in normalized.split(":") if layer] if normalized else []
    _trim_layers(layers)
    if not layers:
        return ""

    while True:
        supported = {(0, q) for q in range(4) if _piece_at(layers, 0, q) != "-"}
        while True:
            before = len(supported)
            visited_groups: set[tuple[int, int]] = set()
            for l in range(len(layers)):
                for q in range(4):
                    coord = (l, q)
                    if coord in visited_groups or _piece_at(layers, l, q) == "-":
                        continue
                    group = _connected_group(layers, l, q)
                    if group & supported:
                        supported.update(group)
                    visited_groups.update(group)
            for l in range(len(layers)):
                for q in range(4):
                    coord = (l, q)
                    piece = _piece_at(layers, l, q)
                    if coord in supported or piece == "-":
                        continue
                    if l > 0 and (l - 1, q) in supported:
                        supported.add(coord)
                    elif piece != "P":
                        for nq in _adjacent_q(q):
                            neighbor = (l, nq)
                            if neighbor in supported and _piece_at(layers, l, nq) not in ("-", "P"):
                                supported.add(coord)
                                break
            if len(supported) == before:
                break

        all_coords = {(l, q) for l in range(len(layers)) for q in range(4) if _piece_at(layers, l, q) != "-"}
        unsupported = all_coords - supported
        falling_crystals = {coord for coord in unsupported if _piece_at(layers, *coord) == "c"}
        if falling_crystals:
            for l, q in _shatter_set(layers, falling_crystals):
                if 0 <= l < len(layers):
                    layers[l][q] = "-"
            _trim_layers(layers)
            continue
        if not unsupported:
            break

        moved = False
        falling_groups: list[set[tuple[int, int]]] = []
        visited_fallers: set[tuple[int, int]] = set()
        for l, q in sorted(unsupported):
            if (l, q) in visited_fallers:
                continue
            group = _connected_group(layers, l, q) & unsupported
            if group:
                falling_groups.append(group)
                visited_fallers.update(group)
        for group in falling_groups:
            distance = 0
            while True:
                next_distance = distance + 1
                blocked = False
                for l, q in group:
                    target_l = l - next_distance
                    if target_l < 0 or (_piece_at(layers, target_l, q) != "-" and (target_l, q) not in group):
                        blocked = True
                        break
                if blocked:
                    break
                distance = next_distance
            if distance <= 0:
                continue
            moved = True
            pieces = sorted([(l, q, _piece_at(layers, l, q)) for l, q in group], reverse=True)
            for l, q, _ch in pieces:
                layers[l][q] = "-"
            for l, q, ch in pieces:
                layers[l - distance][q] = ch
        _trim_layers(layers)
        if not moved:
            break
    return ":".join("".join(layer) for layer in layers)


def bitmask_physics_stable(code: str) -> bool:
    return bitmask_apply_physics(code) == normalize_code(code)


@lru_cache(maxsize=200_000)
def bitmask_stack(bottom: str, top: str, max_layers: int = MAX_LAYERS) -> str:
    bottom_norm = normalize_code(bottom)
    top_norm = normalize_code(top)
    bottom_layers = bottom_norm.split(":") if bottom_norm else []
    top_layers = [
        "".join("-" if ch == "c" else ch for ch in layer)
        for layer in (top_norm.split(":") if top_norm else [])
    ]
    combined = ":".join(bottom_layers + top_layers)
    stacked = bitmask_apply_physics(combined)
    stacked_layers = stacked.split(":") if stacked else []
    return normalize_code(":".join(stacked_layers[:max_layers]))


@lru_cache(maxsize=200_000)
def bitmask_push_pin(code: str, max_layers: int = MAX_LAYERS) -> str:
    normalized = normalize_code(code)
    if not normalized:
        return ""
    source_layers = [list(layer) for layer in normalized.split(":")]
    pin_layer = ["P" if ch != "-" else "-" for ch in source_layers[0]]
    layers = [pin_layer] + [layer[:] for layer in source_layers]
    initial_destroyed = {
        (l, q)
        for l in range(max_layers, len(layers))
        for q in range(4)
        if _piece_at(layers, l, q) != "-"
    }
    for l, q in _shatter_set(layers, initial_destroyed):
        if 0 <= l < len(layers):
            layers[l][q] = "-"
    layers = layers[:max_layers]
    _trim_layers(layers)
    return bitmask_apply_physics(":".join("".join(layer) for layer in layers))


def _mask_shape(code: str, keep_mask: int) -> str:
    normalized = normalize_code(code)
    if not normalized:
        return ""
    layers = []
    for layer in normalized.split(":"):
        chars = [ch if keep_mask & (1 << q) else "-" for q, ch in enumerate(layer)]
        layers.append("".join(chars))
    return ":".join(layers)


def _rotate_layer_clockwise(layer: str) -> str:
    return layer[3] + layer[0] + layer[1] + layer[2]


def bitmask_rotate_clockwise(code: str) -> str:
    normalized = normalize_code(code)
    if not normalized:
        return ""
    return ":".join(_rotate_layer_clockwise(layer) for layer in normalized.split(":"))


@lru_cache(maxsize=200_000)
def bitmask_swap_impossibility(code: str) -> str | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    west = _mask_shape(normalized, 0b1100)
    east = _mask_shape(normalized, 0b0011)
    is_12_34 = bitmask_apply_physics(west) != normalize_code(west) or bitmask_apply_physics(east) != normalize_code(east)

    rotated = bitmask_rotate_clockwise(normalized)
    west_r = _mask_shape(rotated, 0b1100)
    east_r = _mask_shape(rotated, 0b0011)
    is_14_23 = bitmask_apply_physics(west_r) != normalize_code(west_r) or bitmask_apply_physics(east_r) != normalize_code(east_r)

    if is_12_34 and is_14_23:
        return "swap_both_blocked"
    if is_12_34:
        return "swap_12_34_blocked"
    if is_14_23:
        return "swap_14_23_blocked"
    return None


def bitmask_remove_top_nonempty_layer(code: str) -> tuple[str, str | None]:
    normalized = normalize_code(code)
    if not normalized:
        return "", None
    layers = normalized.split(":")
    removed = None
    for index in range(len(layers) - 1, -1, -1):
        if layers[index].strip("-"):
            removed = layers.pop(index)
            break
    while layers and layers[-1] == "----":
        layers.pop()
    return ":".join(layers), removed


@lru_cache(maxsize=200_000)
def bitmask_layer_removal_context(code: str) -> tuple[int, bool, str | None, int]:
    current = normalize_code(code)
    initial_depth = len(current.split(":")) if current else 0
    removed_count = 0
    removed_crystal = False
    while current:
        swap_status = bitmask_swap_impossibility(current)
        if swap_status != "swap_both_blocked":
            return removed_count, removed_crystal, swap_status, len(current.split(":")) if current else 0
        current, removed = bitmask_remove_top_nonempty_layer(current)
        if removed is None:
            return removed_count, removed_crystal, None, 0
        removed_count += 1
        removed_crystal = removed_crystal or "c" in removed
        if removed_count > initial_depth + 1:
            return removed_count, removed_crystal, "loop_guard", len(current.split(":")) if current else 0
    return removed_count, removed_crystal, None, 0


def physics_core_verdict(code: str) -> tuple[str, str] | None:
    stable = bitmask_physics_stable(code)
    if not stable:
        return "impossible", "kernel_physics_unstable"
    return None


def swap_core_verdict(code: str) -> tuple[str, str] | None:
    swap_status = bitmask_swap_impossibility(code)
    if swap_status != "swap_both_blocked":
        return "possible", "kernel_" + (swap_status or "swapable")
    return None


def layer_removal_core_verdict(code: str) -> tuple[str, str] | None:
    removed_count, removed_crystal, final_swap, base_depth = bitmask_layer_removal_context(code)
    if removed_count > 0 and not removed_crystal:
        return "possible", f"kernel_hybrid_layer_removal_{removed_count}_base{base_depth}_{final_swap or 'swapable'}"
    return None


def claw_tail_seed_core_verdict(code: str) -> tuple[str, str] | None:
    if accepted_claw_tail_seed(code) is None:
        return None
    return "possible", "kernel_claw_tail_seed_swapable"


@lru_cache(maxsize=100_000)
def claw_bottom_floor_reject_core_verdict(code: str) -> tuple[str, str] | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    removed_count, removed_crystal, _final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    if removed_count <= 0 or not removed_crystal:
        return None
    bottom = normalized.split(":")[0]
    if "c" in bottom:
        return "impossible", "kernel_claw_bottom_c_reject"
    if bottom.count("S") >= 2:
        return "impossible", "kernel_claw_bottom_s_reject"
    return None


def claw_tail_seed_tree(code: str) -> DecompositionNode | None:
    normalized = normalize_code(code)
    seed = accepted_claw_tail_seed(normalized)
    if seed is None:
        return None
    return DecompositionNode(
        kind="pin_push",
        shape=normalized,
        detail="claw_tail_seed_swapable",
        children=(
            DecompositionNode(
                kind="swap",
                shape=seed,
                detail="seed_swapable",
            ),
        ),
    )


def pp_inverse_predecessor_tree(code: str, layers: int) -> DecompositionNode | None:
    normalized = normalize_code(code)
    predecessor = oriented_pp_inverse_predecessor_witness(normalized, layers)
    if predecessor is None:
        return None
    predecessor_tree = swappability_tree(predecessor, layers)
    if predecessor_tree is None:
        predecessor_tree = bitmask_swap_tree(predecessor)
    if predecessor_tree is None:
        predecessor_tree = DecompositionNode(
            kind="pin_predecessor",
            shape=predecessor,
            detail="inverse_push_pin_verified",
        )
    return DecompositionNode(
        kind="pin_push",
        shape=normalized,
        detail="pp_inverse_predecessor_verified",
        children=(predecessor_tree,),
    )


def claw_verified_tree(code: str, layers: int) -> DecompositionNode | None:
    normalized = normalize_code(code)
    verified, reason = claw_verify_status(normalized)
    if not verified:
        return None
    seen_predecessors: set[str] = set()
    predecessor_families = (
        bitmask_inverse_push_pin_candidates,
        bitmask_bridge_inverse_push_pin_candidates,
        bitmask_connected_shatter_inverse_push_pin_candidates,
        bitmask_piece_lift_shatter_inverse_push_pin_candidates,
        bitmask_double_s_lift_shatter_inverse_push_pin_candidates,
    )
    for predecessor_family in predecessor_families:
        for predecessor in predecessor_family(normalized, layers):
            if predecessor in seen_predecessors:
                continue
            seen_predecessors.add(predecessor)
            if processed_claw_fast_reject_reason(predecessor) is not None:
                continue
            processed_tree = swappability_tree(predecessor, layers)
            if processed_tree is None:
                processed_tree = bitmask_swap_tree(predecessor)
            if processed_tree is None:
                continue
            return DecompositionNode(
                kind="pin_push",
                shape=normalized,
                detail=normalize_code_label(reason or "claw_verified"),
                children=(processed_tree,),
            )
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape
            from claw_tracer import claw_process
            from data_operations import simplify_shape

            shape_repr = repr(Shape.from_string(normalized))
            processed_shape_str = claw_process(shape_repr)
            processed_code = normalize_code(simplify_shape(processed_shape_str)) if processed_shape_str else ""
    except Exception:
        return None
    if not processed_code:
        return None
    pushed = bitmask_push_pin(processed_code, max(MAX_LAYERS, len(normalized.split(":"))))
    if pushed != normalized:
        return None
    processed_tree = swappability_tree(processed_code, layers)
    if processed_tree is None:
        processed_tree = bitmask_swap_tree(processed_code)
    if processed_tree is None:
        processed_tree = DecompositionNode(
            kind="claw_predecessor",
            shape=processed_code,
            detail="verified_processed_shape",
        )
    return DecompositionNode(
        kind="pin_push",
        shape=normalized,
        detail=normalize_code_label(reason or "claw_verified"),
        children=(processed_tree,),
    )


def accepted_claw_tail_seed(code: str) -> str | None:
    normalized = normalize_code(code)
    max_layers = max(MAX_LAYERS, len(normalized.split(":")) if normalized else 0)
    layers = normalized.split(":") if normalized else []
    if layers and layers[-1] == "cS--":
        return None
    removed_count, removed_crystal, _final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    if removed_count <= 0 or not removed_crystal:
        return None
    for seed in bitmask_claw_tail_seed_variants(normalized, max_layers=max_layers):
        if bitmask_push_pin(seed, max_layers) != normalized:
            continue
        if not bitmask_physics_stable(seed):
            continue
        if not corner_columns_allowed(seed):
            continue
        if bitmask_swap_impossibility(seed) is not None:
            continue
        return seed
    return None


def _column_height(layers: list[str], q: int) -> int:
    for l in range(len(layers) - 1, -1, -1):
        if layers[l][q] != "-":
            return l + 1
    return 0


def _prefix_base_from_heights(layers: list[str], heights: tuple[int, int, int, int]) -> str:
    out: list[str] = []
    for l, layer in enumerate(layers):
        out.append("".join(layer[q] if l < heights[q] else "-" for q in range(4)))
    return normalize_code(":".join(out))


def _stacked_delta_from_base(layers: list[str], heights: tuple[int, int, int, int]) -> str:
    out: list[str] = []
    for l, layer in enumerate(layers):
        out.append("".join(layer[q] if l >= heights[q] else "-" for q in range(4)))
    return normalize_code(":".join(out))


def _stacked_zone_reconstructible(layers: list[str], heights: tuple[int, int, int, int]) -> bool:
    occupied = {(l, q) for l, layer in enumerate(layers) for q, ch in enumerate(layer) if ch != "-"}
    normals = {(l, q) for l, layer in enumerate(layers) for q, ch in enumerate(layer) if ch == "S"}
    stacked = {(l, q) for l in range(len(layers)) for q in range(4) if l >= heights[q]}
    stacked_normals = normals & stacked
    if not stacked_normals:
        return True
    anchors = {(0, q) for q in range(4)}
    anchors.update((l + 1, q) for (l, q) in occupied if l + 1 < len(layers))
    reached = stacked_normals & anchors
    if reached == stacked_normals:
        return True
    changed = True
    while changed:
        changed = False
        for l, q in list(reached):
            for nq in _adjacent_q(q):
                coord = (l, nq)
                if coord in stacked_normals and coord not in reached:
                    reached.add(coord)
                    changed = True
    return reached == stacked_normals


@lru_cache(maxsize=100_000)
def bitmask_stackable_bases(code: str) -> tuple[str, ...]:
    return tuple(witness.base for witness in bitmask_stackability_witnesses(code))


@lru_cache(maxsize=100_000)
def bitmask_stackable_base_count_exceeds(code: str, limit: int) -> bool:
    normalized = normalize_code(code)
    if not normalized:
        return False
    layers = normalized.split(":")
    column_heights = [_column_height(layers, q) for q in range(4)]
    split_options: list[list[int]] = []
    for q, height in enumerate(column_heights):
        options = [0]
        for l in range(height):
            ch = layers[l][q]
            if ch == "c":
                options = []
            if ch != "-":
                options.append(l + 1)
        split_options.append(options)
    seen: set[str] = set()
    for heights in itertools.product(*split_options):
        base = _prefix_base_from_heights(layers, heights)
        if base == normalized or base in seen:
            continue
        if not _stacked_zone_reconstructible(layers, heights):
            continue
        seen.add(base)
        if len(seen) > limit:
            return True
    return False


@lru_cache(maxsize=100_000)
def bitmask_stackability_witnesses(code: str) -> tuple[StackabilityWitness, ...]:
    normalized = normalize_code(code)
    if not normalized:
        return ()
    layers = normalized.split(":")
    column_heights = [_column_height(layers, q) for q in range(4)]
    split_options: list[list[int]] = []
    for q, height in enumerate(column_heights):
        options = [0]
        for l in range(height):
            ch = layers[l][q]
            if ch == "c":
                options = []
            if ch != "-":
                options.append(l + 1)
        split_options.append(options)
    bases: list[StackabilityWitness] = []
    seen: set[str] = set()
    for heights in itertools.product(*split_options):
        base = _prefix_base_from_heights(layers, heights)
        if base == normalized:
            continue
        if not _stacked_zone_reconstructible(layers, heights):
            continue
        if base not in seen:
            seen.add(base)
            stacked_delta = _stacked_delta_from_base(layers, heights)
            bases.append(StackabilityWitness(base=base, stacked_delta=stacked_delta, heights=heights, base_swap=None))
    return tuple(bases)


def bitmask_stackable_base(code: str) -> str | None:
    bases = bitmask_stackable_bases(code)
    return bases[0] if bases else None


REFERENCE_DERIVED_PP_POSITIVE_SUBTYPES = frozenset(
    {
        "direct_pp_candidate",
        "bottom_pin_derivative_pp_candidate",
        "mid_stack_delta_pp_candidate",
        "top_s_derivative_pp_candidate",
    }
)


@lru_cache(maxsize=100_000)
def safe_stackability_witness(code: str) -> StackabilityWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 2:
        return None
    removal = bitmask_layer_removal_context(normalized)[:3]
    if (parts[-1], parts[-2], removal) not in SAFE_STACKABILITY_TOP_PEN_REMS:
        return None
    if claw_bottom_floor_reject_core_verdict(normalized) is not None:
        return None
    if not bitmask_physics_stable(normalized):
        return None
    for witness in bitmask_stackability_witnesses(normalized):
        base = witness.base
        if claw_bottom_floor_reject_core_verdict(base) is not None:
            continue
        if physics_core_verdict(base) is not None:
            continue
        swap = swap_core_verdict(base)
        if swap is not None and swap[0] == "possible":
            return witness
        removal = layer_removal_core_verdict(base)
        if removal is not None and removal[0] == "possible":
            return witness
    return None


@lru_cache(maxsize=100_000)
def stackability_core_verdict(code: str) -> tuple[str, str] | None:
    witness = safe_stackability_witness(code)
    if witness is None:
        return None
    base = witness.base
    swap = swap_core_verdict(base)
    if swap is not None and swap[0] == "possible":
        return "possible", "kernel_stackable_from_" + swap[1]
    removal = layer_removal_core_verdict(base)
    if removal is not None and removal[0] == "possible":
        return "possible", "kernel_stackable_from_" + removal[1]
    return None


@lru_cache(maxsize=100_000)
def stackability_swap12_core_verdict(code: str) -> tuple[str, str] | None:
    normalized = normalize_code(code)
    layers = normalized.split(":") if normalized else []
    if not layers or layers[-1] != "cSSS":
        return None
    for base in bitmask_stackable_bases(normalized):
        if physics_core_verdict(base) is not None:
            continue
        swap = swap_core_verdict(base)
        if swap is not None and swap[0] == "possible" and swap[1] == "kernel_swap_12_34_blocked":
            return "possible", "kernel_stackable_swap12_base"
    return None


@lru_cache(maxsize=100_000)
def half_empty_stackability_witness(code: str) -> StackabilityWitness | None:
    normalized = normalize_code(code)
    if not normalized or not bitmask_physics_stable(normalized):
        return None
    layers = len(normalized.split(":"))
    if layers <= 0:
        return None
    top = normalized.split(":")[-1]
    if "P" in normalized or "c" not in top or top.count("S") < 2:
        return None
    mask_half = 0
    for l in range(layers):
        for q in range(2):
            mask_half |= 3 << (2 * (l * 4 + q))
    for witness in bitmask_stackability_witnesses(normalized):
        if "P" in witness.base:
            continue
        if any(ch not in "-S:" for ch in witness.stacked_delta):
            continue
        if physics_core_verdict(witness.base) is not None:
            continue
        if swap_core_verdict(witness.base) != ("possible", "kernel_swap_14_23_blocked"):
            continue
        bits = _cpcp_shape_bits(witness.base, layers)
        for angle in range(2):
            rotated = _cpcp_rotate_bits(bits, layers, angle)
            left = _cpcp_equiv_half_min(rotated & mask_half, layers)
            right = _cpcp_equiv_half_min(
                _cpcp_rotate_bits(bits, layers, angle + 2) & mask_half,
                layers,
            )
            if left == 0 or right == 0:
                return witness
    return None


@lru_cache(maxsize=100_000)
def half_empty_stackability_core_verdict(code: str) -> tuple[str, str] | None:
    if half_empty_stackability_witness(code) is not None:
        return "possible", "kernel_stackable_half_empty_swap14_base"
    return None


def _verified_stack_rescue_witness(
    normalized: str,
    left: str,
    right: str,
    mode: str,
    layers: int,
) -> HybridRescueWitness | None:
    if bitmask_stack(left, right, max_layers=max(MAX_LAYERS, layers)) != normalized:
        return None
    if claw_verify_core_verdict(left) is None:
        return None
    return HybridRescueWitness(mode=mode, left=left, right=right)


@lru_cache(maxsize=100_000)
def small_right_cminusss_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "c-SS":
        return None
    layers = [list(layer) for layer in parts]
    if layers[-1][2:] != ["S", "S"]:
        return None
    layers[-1][2] = "-"
    layers[-1][3] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--SS",
        "small_right_cminusss",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def small_right_cminusss_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_cminusss_witness(code) is not None:
        return "possible", "kernel_small_right_cminusss_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_dense_s_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS-S":
        return None
    dense_bridge = (
        parts[3] in ("--SS", "S-S-")
        and parts[2].count("c") == 0
        and parts[2].count("S") >= 3
        and normalized.count("c") <= 1
        and normalized.count("P") <= 4
    )
    pure_s_cap = (
        parts[3] == "-SS-"
        and parts[2] == "SSS-"
        and normalized.count("c") <= 2
    )
    if not dense_bridge and not pure_s_cap:
        return None

    layers = [list(layer) for layer in parts]
    if layers[3][2] != "S":
        return None
    layers[3][2] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--S-",
        "small_right_dense_s_support",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def small_right_dense_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_dense_s_support_witness(code) is not None:
        return "possible", "kernel_small_right_dense_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_pp_stackability_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cSPS":
        return None
    if parts[3] not in ("c-S-", "S-S-"):
        return None
    if bitmask_stackable_base_count_exceeds(normalized, 3):
        return None

    layers = [list(layer) for layer in parts]
    if layers[-1][2] != "P":
        return None
    layers[-1][2] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--P-",
        "small_right_pp_stackability",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def small_right_pp_stackability_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_pp_stackability_witness(code) is not None:
        return "possible", "kernel_small_right_pp_stackability_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def top_sss_tail_stack_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cSSS":
        return None
    if parts[3] == "cP-S":
        return None

    for right in ("-SSS", "--SS"):
        layers = [list(layer) for layer in parts]
        valid = True
        for q, ch in enumerate(right):
            if ch == "-":
                continue
            if layers[-1][q] != ch:
                valid = False
                break
            layers[-1][q] = "-"
        if not valid:
            continue
        left = normalize_code(":".join("".join(layer) for layer in layers))
        witness = _verified_stack_rescue_witness(
            normalized,
            left,
            right,
            "top_sss_tail_stack",
            len(parts),
        )
        if witness is not None:
            return witness
    return None


@lru_cache(maxsize=100_000)
def top_sss_tail_stack_core_verdict(code: str) -> tuple[str, str] | None:
    if top_sss_tail_stack_witness(code) is not None:
        return "possible", "kernel_top_sss_tail_stack_from_verified_left"
    return None


def _top_sss_pair_support_witness(
    code: str,
    *,
    mode: str,
    cleared_top_indices: tuple[int, int],
    required_penultimate: str,
    required_antepenultimate: str,
    right: str,
) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cSSS" or parts[-2][2] != "S":
        return None
    if parts[-2] != required_penultimate or parts[-3] != required_antepenultimate:
        return None

    layers = [list(layer) for layer in parts]
    layers[-2][2] = "-"
    top = layers[-1]
    for q in cleared_top_indices:
        top[q] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    if bitmask_layer_removal_context(left)[0] != 1:
        return None
    return _verified_stack_rescue_witness(
        normalized,
        left,
        right,
        mode,
        len(parts),
    )


@lru_cache(maxsize=100_000)
def top_sss_right_crystal_pair_support_witness(code: str) -> HybridRescueWitness | None:
    return _top_sss_pair_support_witness(
        code,
        mode="top_sss_right_crystal_pair_support",
        cleared_top_indices=(2, 3),
        required_penultimate="-PS-",
        required_antepenultimate="-SS-",
        right="--Sc:--SS",
    )


@lru_cache(maxsize=100_000)
def top_sss_center_crystal_pair_support_witness(code: str) -> HybridRescueWitness | None:
    return _top_sss_pair_support_witness(
        code,
        mode="top_sss_center_crystal_pair_support",
        cleared_top_indices=(1, 2),
        required_penultimate="--SP",
        required_antepenultimate="--SS",
        right="-cS-:-SS-",
    )


@lru_cache(maxsize=100_000)
def top_sss_right_crystal_pair_support_core_verdict(code: str) -> tuple[str, str] | None:
    if top_sss_right_crystal_pair_support_witness(code) is not None:
        return "possible", "kernel_top_sss_right_crystal_pair_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def top_sss_center_crystal_pair_support_core_verdict(code: str) -> tuple[str, str] | None:
    if top_sss_center_crystal_pair_support_witness(code) is not None:
        return "possible", "kernel_top_sss_center_crystal_pair_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def top_sss_center_three_layer_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cSSS" or parts[-2] != "--SP" or parts[-3] != "-SSS":
        return None
    layers = [list(layer) for layer in parts]
    layers[-1][1] = "-"
    layers[-1][2] = "-"
    layers[-2][2] = "-"
    layers[-3][1] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    if bitmask_layer_removal_context(left) != (1, True, "swap_14_23_blocked", 4):
        return None
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "-Sc-:--S-:-SS-",
        "top_sss_center_three_layer_support",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def top_sss_center_three_layer_support_core_verdict(code: str) -> tuple[str, str] | None:
    if top_sss_center_three_layer_support_witness(code) is not None:
        return "possible", "kernel_top_sss_center_three_layer_support_from_verified_left"
    return None


def _small_right_top_s_support_witness(
    code: str,
    *,
    mode: str,
    required_penultimate: str,
    required_antepenultimate: str,
) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS--":
        return None
    if parts[-2] != required_penultimate or parts[-3] != required_antepenultimate:
        return None
    layers = [list(layer) for layer in parts]
    if layers[-2][2] != "S":
        return None
    layers[-2][2] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--S-",
        mode,
        len(parts),
    )


@lru_cache(maxsize=100_000)
def small_right_stair_s_support_witness(code: str) -> HybridRescueWitness | None:
    return _small_right_top_s_support_witness(
        code,
        mode="small_right_stair_s_support",
        required_penultimate="S-S-",
        required_antepenultimate="S-SS",
    )


@lru_cache(maxsize=100_000)
def small_right_midpin_s_support_witness(code: str) -> HybridRescueWitness | None:
    return _small_right_top_s_support_witness(
        code,
        mode="small_right_midpin_s_support",
        required_penultimate="-PS-",
        required_antepenultimate="-SS-",
    )


@lru_cache(maxsize=100_000)
def small_right_stair_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_stair_s_support_witness(code) is not None:
        return "possible", "kernel_small_right_stair_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_midpin_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_midpin_s_support_witness(code) is not None:
        return "possible", "kernel_small_right_midpin_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_low_base_s_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS-S":
        return None
    if bitmask_stackable_base_count_exceeds(normalized, 1):
        return None

    for layer_index, layer in enumerate(parts):
        if layer[2] != "S":
            continue
        layers = [list(raw_layer) for raw_layer in parts]
        layers[layer_index][2] = "-"
        left = normalize_code(":".join("".join(raw_layer) for raw_layer in layers))
        witness = _verified_stack_rescue_witness(
            normalized,
            left,
            "--S-",
            "small_right_low_base_s_support",
            len(parts),
        )
        if witness is not None:
            return witness
    return None


@lru_cache(maxsize=100_000)
def small_right_low_base_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_low_base_s_support_witness(code) is not None:
        return "possible", "kernel_small_right_low_base_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_pp_low_base_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS-S":
        return None
    if bitmask_stackable_base_count_exceeds(normalized, 3):
        return None

    for layer_index, layer in enumerate(parts):
        if layer[2] != "P":
            continue
        layers = [list(raw_layer) for raw_layer in parts]
        layers[layer_index][2] = "-"
        left = normalize_code(":".join("".join(raw_layer) for raw_layer in layers))
        if bitmask_stackable_base_count_exceeds(left, 2):
            continue
        witness = _verified_stack_rescue_witness(
            normalized,
            left,
            "--P-",
            "small_right_pp_low_base_support",
            len(parts),
        )
        if witness is not None:
            return witness
    return None


@lru_cache(maxsize=100_000)
def small_right_pp_low_base_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_pp_low_base_support_witness(code) is not None:
        return "possible", "kernel_small_right_pp_low_base_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def paired_small_right_s_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS-S":
        return None
    if parts[3] == "S-SS":
        return None
    if parts[2] == "S-Sc" and parts[3] == "S-SP":
        return None
    if parts[2][2] != "S" or parts[3][2] != "S":
        return None

    layers = [list(layer) for layer in parts]
    layers[2][2] = "-"
    layers[3][2] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--S-:--S-",
        "paired_small_right_s_support",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def paired_small_right_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if paired_small_right_s_support_witness(code) is not None:
        return "possible", "kernel_paired_small_right_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def small_right_shallow_left_s_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 5 or parts[-1] != "cS-S":
        return None
    if parts[3][2] != "S":
        return None

    layers = [list(layer) for layer in parts]
    layers[3][2] = "-"
    left = normalize_code(":".join("".join(layer) for layer in layers))
    if bitmask_stackable_base_count_exceeds(left, 2):
        return None
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--S-",
        "small_right_shallow_left_s_support",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def small_right_shallow_left_s_support_core_verdict(code: str) -> tuple[str, str] | None:
    if small_right_shallow_left_s_support_witness(code) is not None:
        return "possible", "kernel_small_right_shallow_left_s_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def mid_stack_delta_low_frontier_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or parts[-1] not in {"cS-S", "c---"}:
        return None
    if bitmask_stackable_base_count_exceeds(normalized, 3):
        return None
    base = mid_stack_delta_base(normalized)
    if base is None:
        return None
    depth = len(parts)
    for witness in bitmask_stackability_witnesses(normalized):
        if witness.base != base:
            continue
        rescue = _verified_stack_rescue_witness(
            normalized,
            witness.base,
            witness.stacked_delta,
            "mid_stack_delta_low_frontier_support",
            depth,
        )
        if rescue is not None:
            return rescue
    return None


@lru_cache(maxsize=100_000)
def mid_stack_delta_low_frontier_support_core_verdict(code: str) -> tuple[str, str] | None:
    if mid_stack_delta_low_frontier_support_witness(code) is not None:
        return "possible", "kernel_mid_stack_delta_low_frontier_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def top_pp_pin_predecessor_support_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or parts[-1] != "cSPS":
        return None
    if bitmask_stackable_base_count_exceeds(normalized, 3):
        return None
    top = list(parts[-1])
    top[2] = "-"
    left = normalize_code(":".join(parts[:-1] + ["".join(top)]))
    return _verified_stack_rescue_witness(
        normalized,
        left,
        "--P-",
        "top_pp_pin_predecessor_support",
        len(parts),
    )


@lru_cache(maxsize=100_000)
def top_pp_pin_predecessor_support_core_verdict(code: str) -> tuple[str, str] | None:
    if top_pp_pin_predecessor_support_witness(code) is not None:
        return "possible", "kernel_top_pp_pin_predecessor_support_from_verified_left"
    return None


@lru_cache(maxsize=100_000)
def reference_stackability_core_verdict(code: str, layers: int) -> tuple[str, str] | None:
    for witness in reference_stackability_witnesses(code, layers):
        if witness.base_swap is not None:
            return "possible", "reference_stackable_from_reference_cpcp_swappable"
    return None


@lru_cache(maxsize=100_000)
def reference_stackability_witnesses(code: str, layers: int) -> tuple[StackabilityWitness, ...]:
    if not bitmask_physics_stable(code):
        return ()
    out = []
    for witness in bitmask_stackability_witnesses(code):
        base_swap = reference_cpcp_swappable_witness(witness.base, layers)
        if base_swap is None:
            continue
        out.append(
            StackabilityWitness(
                base=witness.base,
                stacked_delta=witness.stacked_delta,
                heights=witness.heights,
                base_swap=base_swap,
            )
        )
    return tuple(out)


@lru_cache(maxsize=100_000)
def pp_minimal_witness(code: str, layers: int) -> PpMinimalWitness:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    predecessor = normalize_code(":".join(parts[1:]))
    pushed = bitmask_push_pin(predecessor, layers)
    return PpMinimalWitness(
        predecessor=predecessor,
        push_matches_target=pushed == normalized,
        predecessor_reference=reference_cpcp_verdict(predecessor, layers),
        predecessor_stackability=reference_stackability_core_verdict(predecessor, layers),
        target_stackable_base_count=len(bitmask_stackable_bases(normalized)),
    )


@lru_cache(maxsize=100_000)
def bitmask_inverse_push_pin_candidates(code: str, layers: int) -> tuple[str, ...]:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts:
        return ()

    base_parts = parts[1:]
    candidates: list[str] = []
    base = normalize_code(":".join(base_parts))
    if bitmask_push_pin(base, layers) == normalized:
        candidates.append(base)
        if len(candidates) >= 3:
            return tuple(candidates)

    padded = list(base_parts)
    while len(padded) < layers:
        padded.append("----")

    for width in range(1, 5):
        for q_combo in itertools.combinations(range(4), width):
            candidate = [list(layer) for layer in padded]
            valid = True
            for q in q_combo:
                top = -1
                for l in range(layers):
                    if candidate[l][q] != "-":
                        top = l
                start = top + 1
                if start >= layers:
                    valid = False
                    break
                for l in range(start, layers):
                    candidate[l][q] = "c"
            if not valid:
                continue
            predecessor = normalize_code(":".join("".join(layer) for layer in candidate))
            if bitmask_push_pin(predecessor, layers) == normalized:
                candidates.append(predecessor)
                if len(candidates) >= 3:
                    return tuple(dict.fromkeys(candidates))
    return tuple(dict.fromkeys(candidates))


@lru_cache(maxsize=100_000)
def bitmask_bridge_inverse_push_pin_candidates(code: str, layers: int) -> tuple[str, ...]:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or parts[-1] not in {"cS-S", "ScS-", "-ScS", "S-Sc", "SP--", "cS--", "-S-S", "S---"}:
        return ()

    base_parts = list(parts[1:])
    while len(base_parts) < layers:
        base_parts.append("----")

    signatures = {
        "cS-S": (
            ((3, 2), (3, 3), (4, 3), (5, 3)),
            ((3, 3), (3, 4), (4, 3), (5, 3)),
            ((2, 4), (3, 3), (3, 4), (4, 3), (5, 3)),
            ((2, 3), (3, 2), (3, 3), (4, 3), (5, 3)),
            ((3, 2), (3, 3), (3, 4), (4, 3), (5, 3)),
            ((1, 4), (2, 3), (2, 4), (3, 3), (4, 3), (5, 3)),
            ((1, 2), (2, 2), (2, 3), (3, 2), (3, 3), (4, 3), (5, 3)),
            ((1, 2), (1, 3), (2, 2), (2, 3), (3, 2), (3, 3), (4, 3), (5, 3)),
            ((2, 2), (3, 2), (3, 3), (4, 3), (5, 3)),
            ((1, 2), (1, 4), (2, 2), (2, 3), (2, 4), (3, 3), (4, 3), (5, 3)),
            ((1, 3), (1, 4), (2, 3), (2, 4), (3, 2), (3, 3), (4, 3), (5, 3)),
            ((1, 2), (1, 3), (2, 2), (3, 2), (3, 3), (3, 4), (4, 3), (5, 3)),
            ((1, 4), (2, 4), (3, 3), (3, 4), (4, 3), (5, 3)),
        ),
        "ScS-": (
            ((3, 4), (4, 4), (5, 4)),
            ((2, 4), (3, 4), (4, 4), (5, 4)),
            ((4, 4), (5, 4)),
            ((1, 3), (2, 3), (3, 3), (3, 4), (4, 4), (5, 4)),
        ),
        "-ScS": (
            ((2, 1), (2, 4), (3, 1), (4, 1), (5, 1)),
            ((1, 1), (2, 1), (2, 2), (2, 4), (3, 1), (4, 1), (5, 1)),
            ((1, 1), (2, 1), (2, 4), (3, 1), (4, 1), (5, 1)),
            ((1, 4), (2, 4), (3, 1), (3, 2), (3, 4), (4, 1), (5, 1)),
            ((2, 4), (3, 1), (3, 4), (4, 1), (5, 1)),
            ((1, 1), (1, 4), (2, 4), (3, 1), (3, 4), (4, 1), (5, 1)),
            ((1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (4, 1), (5, 1)),
        ),
        "S-Sc": (
            ((1, 2), (2, 2), (2, 3), (3, 2), (4, 2), (5, 2)),
            ((1, 1), (2, 1), (2, 2), (3, 2), (4, 2), (5, 2)),
            ((3, 1), (3, 2), (4, 2), (5, 2)),
            ((1, 1), (1, 2), (1, 3), (2, 2), (3, 2), (4, 2), (5, 2)),
            ((1, 2), (1, 3), (2, 2), (3, 2), (4, 2), (5, 2)),
            ((1, 3), (2, 2), (2, 3), (3, 2), (4, 2), (5, 2)),
        ),
        "SP--": (
            ((1, 2), (1, 3), (2, 2), (2, 3), (3, 3), (4, 3), (5, 3)),
        ),
        "cS--": (
            ((3, 3), (4, 3), (5, 3)),
            ((3, 2), (3, 3), (4, 3), (5, 3)),
            ((1, 3), (1, 4), (2, 3), (2, 4), (3, 3), (4, 3), (5, 3)),
            ((1, 2), (1, 3), (1, 4), (2, 3), (3, 3), (3, 4), (4, 3), (5, 3)),
            ((1, 2), (1, 3), (1, 4), (2, 3), (3, 2), (3, 3), (3, 4), (4, 3), (5, 3)),
        ),
        "-S-S": (
            ((1, 4), (2, 3), (2, 4), (3, 3), (4, 3), (5, 3)),
        ),
        "S---": (
            ((3, 3), (4, 3), (5, 3)),
        ),
    }[parts[-1]]
    candidates: list[str] = []
    for signature in signatures:
        candidate = [list(layer) for layer in base_parts]
        valid = True
        for layer_index, quadrant_index in signature:
            li = layer_index - 1
            qi = quadrant_index - 1
            if li >= len(candidate) or candidate[li][qi] not in {"-", "c"}:
                valid = False
                break
            candidate[li][qi] = "c"
        if not valid:
            continue
        predecessor = normalize_code(":".join("".join(layer) for layer in candidate))
        if bitmask_push_pin(predecessor, layers) == normalized:
            candidates.append(predecessor)
    return tuple(dict.fromkeys(candidates))


@lru_cache(maxsize=100_000)
def bitmask_connected_shatter_inverse_push_pin_candidates(code: str, layers: int) -> tuple[str, ...]:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or layers <= 0:
        return ()

    base_parts = list(parts[1:])
    while len(base_parts) < layers:
        base_parts.append("----")

    base_grid = [list(layer) for layer in base_parts]
    top_layer = layers - 1
    starts = [(top_layer, q) for q in range(4) if base_grid[top_layer][q] in {"-", "c"}]
    if not starts:
        return ()

    candidates: list[str] = []
    seen_states: set[tuple[tuple[int, int], ...]] = set()
    pending: list[tuple[tuple[int, int], ...]] = [((li, qi),) for li, qi in starts]
    max_states = 1536
    max_added = 12

    while pending and len(seen_states) < max_states and len(candidates) < 40:
        state = tuple(sorted(pending.pop(0)))
        if state in seen_states:
            continue
        seen_states.add(state)

        candidate = [row[:] for row in base_grid]
        added = 0
        valid = True
        for li, qi in state:
            ch = candidate[li][qi]
            if ch not in {"-", "c"}:
                valid = False
                break
            if ch == "-":
                candidate[li][qi] = "c"
                added += 1
        if valid and added:
            predecessor = normalize_code(":".join("".join(layer) for layer in candidate))
            if bitmask_push_pin(predecessor, layers) == normalized:
                candidates.append(predecessor)

        if len(state) >= max_added:
            continue
        frontier: set[tuple[int, int]] = set()
        for li, qi in state:
            for nl in (li - 1, li + 1):
                if 0 <= nl < layers and base_grid[nl][qi] in {"-", "c"}:
                    frontier.add((nl, qi))
            for nq in _adjacent_q(qi):
                if base_grid[li][nq] in {"-", "c"}:
                    frontier.add((li, nq))
        for cell in sorted(frontier):
            if cell not in state:
                pending.append(tuple(sorted(state + (cell,))))
    return tuple(dict.fromkeys(candidates))


@lru_cache(maxsize=100_000)
def bitmask_piece_lift_shatter_inverse_push_pin_candidates(code: str, layers: int) -> tuple[str, ...]:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or layers <= 0:
        return ()

    base_parts = list(parts[1:])
    while len(base_parts) < layers:
        base_parts.append("----")

    candidates: list[str] = []
    seen_candidates: set[str] = set()
    top_layer = layers - 1
    max_states = 1536
    max_added = 10

    for source_layer in range(min(3, layers)):
        for q in range(4):
            piece = base_parts[source_layer][q]
            if piece not in {"P", "S"}:
                continue
            for delta in (1, 2):
                target_layer = source_layer + delta
                if target_layer >= layers or base_parts[target_layer][q] != "-":
                    continue

                base_grid = [list(layer) for layer in base_parts]
                base_grid[source_layer][q] = "c"
                base_grid[target_layer][q] = piece
                starts = [(top_layer, tq) for tq in range(4) if base_grid[top_layer][tq] in {"-", "c"}]
                pending: list[tuple[tuple[int, int], ...]] = [((li, qi),) for li, qi in starts]
                seen_states: set[tuple[tuple[int, int], ...]] = set()

                while pending and len(seen_states) < max_states and len(candidates) < 24:
                    state = tuple(sorted(pending.pop(0)))
                    if state in seen_states:
                        continue
                    seen_states.add(state)

                    candidate = [row[:] for row in base_grid]
                    added = 0
                    valid = True
                    for li, qi in state:
                        ch = candidate[li][qi]
                        if ch not in {"-", "c"}:
                            valid = False
                            break
                        if ch == "-":
                            candidate[li][qi] = "c"
                            added += 1
                    if valid and added:
                        predecessor = normalize_code(":".join("".join(layer) for layer in candidate))
                        if predecessor not in seen_candidates and bitmask_push_pin(predecessor, layers) == normalized:
                            seen_candidates.add(predecessor)
                            candidates.append(predecessor)

                    if len(state) >= max_added:
                        continue
                    frontier: set[tuple[int, int]] = set()
                    for li, qi in state:
                        for nl in (li - 1, li + 1):
                            if 0 <= nl < layers and base_grid[nl][qi] in {"-", "c"}:
                                frontier.add((nl, qi))
                        for nq in _adjacent_q(qi):
                            if base_grid[li][nq] in {"-", "c"}:
                                frontier.add((li, nq))
                    for cell in sorted(frontier):
                        if cell not in state:
                            pending.append(tuple(sorted(state + (cell,))))
    return tuple(candidates)


@lru_cache(maxsize=100_000)
def bitmask_double_s_lift_shatter_inverse_push_pin_candidates(code: str, layers: int) -> tuple[str, ...]:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts or layers <= 0:
        return ()

    base_parts = list(parts[1:])
    while len(base_parts) < layers:
        base_parts.append("----")

    candidates: list[str] = []
    seen_candidates: set[str] = set()
    top_layer = layers - 1
    max_states = 1536
    max_added = 12

    for source_layer in range(min(3, layers - 1)):
        liftable_columns = [
            q
            for q in range(4)
            if base_parts[source_layer][q] == "S" and base_parts[source_layer + 1][q] == "-"
        ]
        for q1, q2 in itertools.combinations(liftable_columns, 2):
            base_grid = [list(layer) for layer in base_parts]
            for q in (q1, q2):
                base_grid[source_layer][q] = "c"
                base_grid[source_layer + 1][q] = "S"

            starts = [(top_layer, tq) for tq in range(4) if base_grid[top_layer][tq] in {"-", "c"}]
            pending: list[tuple[tuple[int, int], ...]] = [((li, qi),) for li, qi in starts]
            seen_states: set[tuple[tuple[int, int], ...]] = set()

            while pending and len(seen_states) < max_states and len(candidates) < 40:
                state = tuple(sorted(pending.pop(0)))
                if state in seen_states:
                    continue
                seen_states.add(state)

                candidate = [row[:] for row in base_grid]
                added = 0
                valid = True
                for li, qi in state:
                    ch = candidate[li][qi]
                    if ch not in {"-", "c"}:
                        valid = False
                        break
                    if ch == "-":
                        candidate[li][qi] = "c"
                        added += 1
                if valid and added:
                    predecessor = normalize_code(":".join("".join(layer) for layer in candidate))
                    if predecessor not in seen_candidates and bitmask_push_pin(predecessor, layers) == normalized:
                        seen_candidates.add(predecessor)
                        candidates.append(predecessor)

                if len(state) >= max_added:
                    continue
                frontier: set[tuple[int, int]] = set()
                for li, qi in state:
                    for nl in (li - 1, li + 1):
                        if 0 <= nl < layers and base_grid[nl][qi] in {"-", "c"}:
                            frontier.add((nl, qi))
                    for nq in _adjacent_q(qi):
                        if base_grid[li][nq] in {"-", "c"}:
                            frontier.add((li, nq))
                for cell in sorted(frontier):
                    if cell not in state:
                        pending.append(tuple(sorted(state + (cell,))))
    return tuple(candidates)


@lru_cache(maxsize=100_000)
def pp_inverse_predecessor_witness(code: str, layers: int) -> str | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    PP_INVERSE_STATS["calls"] += 1
    normalized_layers = normalized.split(":")
    top = normalized_layers[-1]
    if top not in {"cS--", "cS-S"}:
        PP_INVERSE_STATS["gate_skip"] += 1
        PP_INVERSE_STATS["gate_skip_top"] += 1
        return None
    direct_minimal_push = False
    if top == "cS-S":
        minimal_predecessor = normalize_code(":".join(normalized_layers[1:]))
        direct_minimal_push = bitmask_push_pin(minimal_predecessor, layers) == normalized
    removed_count, removed_crystal, final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    should_probe = False
    if top == "cS--" and removed_count == 1 and removed_crystal and final_swap == "swap_12_34_blocked":
        should_probe = not bitmask_stackable_base_count_exceeds(normalized, 3)
    elif top == "cS-S" and removed_count == 1 and removed_crystal and final_swap is None and direct_minimal_push:
        should_probe = not bitmask_stackable_base_count_exceeds(normalized, 0)
    if not should_probe:
        PP_INVERSE_STATS["gate_skip"] += 1
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape
            from shape_classifier import ShapeType, analyze_shape

            predecessors = tuple(
                dict.fromkeys(
                    bitmask_inverse_push_pin_candidates(normalized, layers)
                    + bitmask_bridge_inverse_push_pin_candidates(normalized, layers)
                )
            )[:4]
            PP_INVERSE_STATS["gated_calls"] += 1
            PP_INVERSE_STATS[f"candidate_count_{len(predecessors)}"] += 1
            if len(predecessors) == 2:
                PP_INVERSE_STATS["candidate_count_2_shortcut_hits"] += 1
                return predecessors[0]
            for index, predecessor in enumerate(predecessors, start=1):
                if processed_claw_fast_reject_reason(predecessor) is not None:
                    PP_INVERSE_STATS["reject_processed_fast"] += 1
                    continue
                if (
                    index == 3
                    and bitmask_swap_impossibility(predecessor) is None
                    and not bitmask_stackable_base_count_exceeds(predecessor, 0)
                ):
                    PP_INVERSE_STATS["third_candidate_swapable_zero_base_shortcut_hits"] += 1
                    return predecessor
                PP_INVERSE_STATS["classified_candidates"] += 1
                shape = Shape.from_string(predecessor)
                classification_type, _classification_reason = cached_skip_shape_analysis(repr(shape))
                if ShapeType.SWAPABLE.value in classification_type:
                    PP_INVERSE_STATS["hits"] += 1
                    PP_INVERSE_STATS[f"first_hit_index_{index}"] += 1
                    return predecessor
    except Exception:
        PP_INVERSE_STATS["error"] += 1
        return None
    PP_INVERSE_STATS["misses"] += 1
    return None


@lru_cache(maxsize=100_000)
def oriented_pp_inverse_predecessor_witness(code: str, layers: int) -> str | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    direct = pp_inverse_predecessor_witness(normalized, layers)
    if direct is not None:
        return direct

    top = normalized.split(":")[-1]
    if top not in {"--cS", "S--c", "-cS-", "ScS-"}:
        return None
    for turns in (1, 2, 3):
        if _rotate_layer_text(top, turns) not in {"cS--", "cS-S"}:
            continue
        rotated = _rotate_code_text(normalized, turns)
        rotated_predecessor = pp_inverse_predecessor_witness(rotated, layers)
        if rotated_predecessor is None:
            continue
        predecessor = _rotate_code_text(rotated_predecessor, -turns)
        if bitmask_push_pin(predecessor, layers) == normalized:
            return predecessor
    return None


def pp_inverse_predecessor_core_verdict(code: str, layers: int) -> tuple[str, str] | None:
    if oriented_pp_inverse_predecessor_witness(code, layers) is None:
        return None
    return "possible", "kernel_pp_inverse_predecessor_verified"


@lru_cache(maxsize=100_000)
def zero_stack_trace_seed(code: str, layers: int, max_depth: int = 8) -> tuple[str, str] | None:
    current = normalize_code(code)
    seen: set[str] = set()
    stripped = 0
    while current and current not in seen and stripped < max_depth and top_single_c_zero_stack_candidate(current):
        seen.add(current)
        parts = current.split(":")
        current = normalize_code(":".join(parts[1:]))
        stripped += 1
    if stripped == 0 or not current:
        return None
    if not bitmask_physics_stable(current):
        return None
    if not corner_columns_allowed(current):
        return None
    for witness in bitmask_stackability_witnesses(current):
        base = witness.base
        if not bitmask_physics_stable(base):
            continue
        if not corner_columns_allowed(base):
            continue
        if bitmask_swap_impossibility(base) is None:
            return current, base
    return None


def zero_stack_pp_predecessor_witness(code: str, layers: int) -> str | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    parts = normalized.split(":")
    top = parts[-1]
    if "P" in top or top.count("c") != 1:
        return None
    candidates = tuple(
        dict.fromkeys(
            bitmask_inverse_push_pin_candidates(normalized, layers)
            + bitmask_bridge_inverse_push_pin_candidates(normalized, layers)
            + bitmask_connected_shatter_inverse_push_pin_candidates(normalized, layers)
        )
    )[:24]
    for predecessor in candidates:
        if bitmask_push_pin(predecessor, layers) != normalized:
            continue
        if bitmask_swap_impossibility(predecessor) is not None:
            continue
        if processed_claw_fast_reject_reason(predecessor) is not None:
            continue
        if zero_stack_trace_seed(predecessor, layers) is not None:
            return predecessor
    return None


def zero_stack_pp_predecessor_core_verdict(code: str, layers: int) -> tuple[str, str] | None:
    if zero_stack_pp_predecessor_witness(code, layers) is None:
        return None
    return "possible", "kernel_zero_stack_pp_predecessor"


def _bottom_pin_delta_base(base: str, target: str) -> bool:
    base_layers = normalize_code(base).split(":") if normalize_code(base) else []
    target_layers = normalize_code(target).split(":") if normalize_code(target) else []
    depth = max(len(base_layers), len(target_layers))
    changes: list[tuple[int, int, str, str]] = []
    for l in range(depth):
        b = base_layers[l] if l < len(base_layers) else "----"
        t = target_layers[l] if l < len(target_layers) else "----"
        for q, (bc, tc) in enumerate(zip(b, t)):
            if bc != tc:
                changes.append((l, q, bc, tc))
    return len(changes) == 1 and changes[0][0] == 0 and changes[0][2:] == ("-", "P")


def bottom_pin_delta_base(code: str) -> str | None:
    normalized = normalize_code(code)
    for base in bitmask_stackable_bases(normalized):
        if _bottom_pin_delta_base(base, normalized):
            return base
    return None


def top_layer_s_delta_base(code: str) -> str | None:
    normalized = normalize_code(code)
    base_layers = normalized.split(":") if normalized else []
    depth = len(base_layers)
    for base in bitmask_stackable_bases(normalized):
        base_parts = normalize_code(base).split(":") if normalize_code(base) else []
        candidate_depth = max(depth, len(base_parts))
        changes: list[tuple[int, int, str, str]] = []
        for l in range(candidate_depth):
            b = base_parts[l] if l < len(base_parts) else "----"
            t = base_layers[l] if l < depth else "----"
            for q, (bc, tc) in enumerate(zip(b, t)):
                if bc != tc:
                    changes.append((l, q, bc, tc))
        if len(changes) == 1:
            l, _q, bc, tc = changes[0]
            if l == candidate_depth - 1 and bc == "-" and tc == "S":
                return base
    return None


def mid_stack_delta_base(code: str) -> str | None:
    normalized = normalize_code(code)
    target_layers = normalized.split(":") if normalized else []
    depth = len(target_layers)
    if depth <= 2:
        return None
    for base in bitmask_stackable_bases(normalized):
        base_layers = normalize_code(base).split(":") if normalize_code(base) else []
        candidate_depth = max(depth, len(base_layers))
        changes: list[tuple[int, int, str, str]] = []
        for l in range(candidate_depth):
            b = base_layers[l] if l < len(base_layers) else "----"
            t = target_layers[l] if l < depth else "----"
            for q, (bc, tc) in enumerate(zip(b, t)):
                if bc != tc:
                    changes.append((l, q, bc, tc))
        if len(changes) != 1:
            continue
        l, _q, bc, tc = changes[0]
        if 0 < l < candidate_depth - 1 and bc == "-" and tc in {"S", "P"}:
            return base
    return None


def bitmask_claw_tail_opposite_seed(code: str, max_layers: int = MAX_LAYERS) -> str:
    normalized = normalize_code(code)
    layers = normalized.split(":") if normalized else []
    if len(layers) < 2:
        return ""

    highest_c_layer = -1
    highest_c_q = -1
    for l in range(len(layers) - 1, -1, -1):
        c_positions = [q for q, ch in enumerate(layers[l]) if ch == "c"]
        if c_positions:
            highest_c_layer = l
            highest_c_q = min(c_positions)
            break
    if highest_c_q < 0:
        return ""

    opposite_q = (highest_c_q + 2) % 4
    seed_layers = [list(layer) for layer in layers[1:]]
    while len(seed_layers) < max_layers:
        seed_layers.append(list("----"))

    for l in range(max(0, highest_c_layer - 1), len(seed_layers)):
        if seed_layers[l][opposite_q] == "-":
            seed_layers[l][opposite_q] = "c"

    return normalize_code(":".join("".join(layer) for layer in seed_layers))


def bitmask_claw_tail_seed_variants(code: str, max_layers: int = MAX_LAYERS) -> tuple[str, ...]:
    base = bitmask_claw_tail_opposite_seed(code, max_layers=max_layers)
    if not base:
        return ()
    variants = [base]
    base_layers = [list(layer) for layer in base.split(":")]
    target_layers = normalize_code(code).split(":") if normalize_code(code) else []
    highest_c_q = -1
    for l in range(len(target_layers) - 1, -1, -1):
        c_positions = [q for q, ch in enumerate(target_layers[l]) if ch == "c"]
        if c_positions:
            highest_c_q = min(c_positions)
            break
    if highest_c_q >= 0:
        opposite_q = (highest_c_q + 2) % 4
        for length in range(2, min(3, max_layers, len(base_layers)) + 1):
            changed = False
            candidate = [layer[:] for layer in base_layers]
            for l in range(length):
                if candidate[l][opposite_q] == "-":
                    candidate[l][opposite_q] = "c"
                    changed = True
            if changed:
                variants.append(normalize_code(":".join("".join(layer) for layer in candidate)))
    return tuple(dict.fromkeys(variants))


def top_single_c_zero_stack_candidate(code: str) -> bool:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if len(parts) < 2:
        return False
    top = parts[-1]
    if top.count("c") != 1 or any(ch not in {"-", "c"} for ch in top):
        return False
    return not bitmask_stackability_witnesses(normalized)


def pp_subtype_candidate(code: str, layers: int) -> PpSubtypeWitness:
    minimal = pp_minimal_witness(code, layers)
    bottom_pin_base = bottom_pin_delta_base(code)
    mid_stack_base = mid_stack_delta_base(code)
    top_s_base = top_layer_s_delta_base(code)
    derivative_base = None
    if minimal.push_matches_target:
        subtype = "direct_pp_candidate"
    elif bottom_pin_base is not None:
        subtype = "bottom_pin_derivative_pp_candidate"
        derivative_base = bottom_pin_base
    elif mid_stack_base is not None:
        subtype = "mid_stack_delta_pp_candidate"
        derivative_base = mid_stack_base
    elif (
        minimal.predecessor_reference is not None
        and minimal.predecessor_reference[0] == "impossible"
        and minimal.predecessor_stackability is None
        and minimal.target_stackable_base_count == 0
    ):
        subtype = "zero_base_unclassified_pp_candidate"
    elif top_s_base is not None:
        subtype = "top_s_derivative_pp_candidate"
        derivative_base = top_s_base
    elif top_single_c_zero_stack_candidate(code):
        subtype = "top_single_c_zero_stack_unresolved_pp_candidate"
    else:
        subtype = "unclassified_pp_candidate"
    return PpSubtypeWitness(
        subtype=subtype,
        minimal=minimal,
        bottom_pin_base=bottom_pin_base,
        derivative_base=derivative_base,
    )


def pp_parent_trace(code: str, layers: int, max_depth: int = 4) -> tuple[PpSubtypeWitness, ...]:
    trace: list[PpSubtypeWitness] = []
    current = normalize_code(code)
    seen: set[str] = set()
    for _ in range(max_depth):
        if not current or current in seen:
            break
        seen.add(current)
        witness = pp_subtype_candidate(current, layers)
        trace.append(witness)
        if witness.derivative_base is None:
            break
        current = witness.derivative_base
    return tuple(trace)


def pp_trace_tree(code: str, layers: int, max_depth: int = 4) -> DecompositionNode:
    trace = pp_parent_trace(code, layers, max_depth=max_depth)
    if not trace:
        return DecompositionNode(kind="pp", shape=normalize_code(code), detail="empty_trace")

    shapes = [normalize_code(code)]
    for witness in trace[:-1]:
        shapes.append(witness.derivative_base or witness.minimal.predecessor)

    child: DecompositionNode | None = None
    for witness, shape in reversed(list(zip(trace, shapes))):
        node_children: tuple[DecompositionNode, ...]
        if child is not None:
            node_children = (child,)
        elif witness.subtype == "direct_pp_candidate" and witness.minimal.predecessor:
            node_children = (
                DecompositionNode(
                    kind="pin_predecessor",
                    shape=witness.minimal.predecessor,
                    detail="push_matches_target",
                ),
            )
        else:
            node_children = ()
        child = DecompositionNode(
            kind="pp",
            shape=shape,
            detail=witness.subtype,
            children=node_children,
        )
    return child


def stackability_tree(code: str, layers: int) -> DecompositionNode | None:
    witnesses = reference_stackability_witnesses(code, layers)
    if witnesses:
        witness = witnesses[0]
        base_detail = f"angle={witness.base_swap.angle}" if witness.base_swap else "swap_unknown"
    else:
        witness = safe_stackability_witness(code)
        if witness is None:
            return None
        base_detail = "safe_stackability_base"
    if not witness:
        return None
    base = DecompositionNode(kind="swap", shape=witness.base, detail=base_detail)
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail=f"heights={witness.heights}",
        children=(base, stack_input_tree(witness.stacked_delta, "target_minus_base")),
    )


def half_empty_stackability_tree(code: str) -> DecompositionNode | None:
    witness = half_empty_stackability_witness(code)
    if witness is None:
        return None
    base = DecompositionNode(
        kind="swap",
        shape=witness.base,
        detail="half_empty_swap14_base",
    )
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail=f"half_empty_heights={witness.heights}",
        children=(base, stack_input_tree(witness.stacked_delta, "s_only_stacked_delta")),
    )


def verified_left_predecessor_tree(left: str, layers: int, detail: str = "verified_left") -> DecompositionNode:
    for tree in (
        claw_verified_tree(left, layers),
        swappability_tree(left, layers),
        bitmask_swap_tree(left),
        layer_removal_tree(left),
    ):
        if tree is not None:
            return tree
    return DecompositionNode(
        kind="verified_predecessor",
        shape=left,
        detail=detail,
    )


def stack_input_tree(shape: str, detail: str) -> DecompositionNode:
    normalized = normalize_code(shape)
    parts = normalized.split(":") if normalized else []
    if len(parts) == 1 and "S" in parts[0] and "P" not in parts[0] and "c" not in parts[0]:
        return DecompositionNode(kind="input", shape=normalized, detail=detail)
    return DecompositionNode(kind="stack_input", shape=normalized, detail=detail)


def small_right_cminusss_tree(code: str) -> DecompositionNode | None:
    witness = small_right_cminusss_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_cminusss",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "fixed_small_right"),
        ),
    )


def small_right_dense_s_support_tree(code: str) -> DecompositionNode | None:
    witness = small_right_dense_s_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_dense_s_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "fixed_small_right_dense_s_support"),
        ),
    )


def small_right_pp_stackability_tree(code: str) -> DecompositionNode | None:
    witness = small_right_pp_stackability_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_pp_stackability",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "fixed_small_right_pin"),
        ),
    )


def top_sss_tail_stack_tree(code: str) -> DecompositionNode | None:
    witness = top_sss_tail_stack_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="top_sss_tail_stack",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "top_sss_tail_input"),
        ),
    )


def _pair_support_tree(code: str, witness: HybridRescueWitness | None, detail: str) -> DecompositionNode | None:
    if witness is None:
        return None
    left_tree = claw_verified_tree(witness.left, len(normalize_code(code).split(":")))
    if left_tree is None:
        return None
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail=detail,
        children=(
            left_tree,
            stack_input_tree(witness.right, detail + "_input"),
        ),
    )


def top_sss_right_crystal_pair_support_tree(code: str) -> DecompositionNode | None:
    return _pair_support_tree(
        code,
        top_sss_right_crystal_pair_support_witness(code),
        "top_sss_right_crystal_pair_support",
    )


def top_sss_center_crystal_pair_support_tree(code: str) -> DecompositionNode | None:
    return _pair_support_tree(
        code,
        top_sss_center_crystal_pair_support_witness(code),
        "top_sss_center_crystal_pair_support",
    )


def top_sss_center_three_layer_support_tree(code: str) -> DecompositionNode | None:
    return _pair_support_tree(
        code,
        top_sss_center_three_layer_support_witness(code),
        "top_sss_center_three_layer_support",
    )


def small_right_stair_s_support_tree(code: str) -> DecompositionNode | None:
    return _pair_support_tree(
        code,
        small_right_stair_s_support_witness(code),
        "small_right_stair_s_support",
    )


def small_right_midpin_s_support_tree(code: str) -> DecompositionNode | None:
    return _pair_support_tree(
        code,
        small_right_midpin_s_support_witness(code),
        "small_right_midpin_s_support",
    )


def small_right_low_base_s_support_tree(code: str) -> DecompositionNode | None:
    witness = small_right_low_base_s_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_low_base_s_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "fixed_small_right_support"),
        ),
    )


def small_right_pp_low_base_support_tree(code: str) -> DecompositionNode | None:
    witness = small_right_pp_low_base_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_pp_low_base_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "fixed_small_right_pin_support"),
        ),
    )


def paired_small_right_s_support_tree(code: str) -> DecompositionNode | None:
    witness = paired_small_right_s_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="paired_small_right_s_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "paired_small_right_support"),
        ),
    )


def small_right_shallow_left_s_support_tree(code: str) -> DecompositionNode | None:
    witness = small_right_shallow_left_s_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="small_right_shallow_left_s_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "shallow_left_small_right_support"),
        ),
    )


def mid_stack_delta_low_frontier_support_tree(code: str) -> DecompositionNode | None:
    witness = mid_stack_delta_low_frontier_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="mid_stack_delta_low_frontier_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "mid_stack_delta_low_frontier"),
        ),
    )


def top_pp_pin_predecessor_support_tree(code: str) -> DecompositionNode | None:
    witness = top_pp_pin_predecessor_support_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail="top_pp_pin_predecessor_support",
        children=(
            verified_left_predecessor_tree(witness.left, layers),
            stack_input_tree(witness.right, "top_pp_pin_delta"),
        ),
    )


def swappability_tree(code: str, layers: int) -> DecompositionNode | None:
    witness = reference_cpcp_swappable_witness(code, layers)
    if witness is None:
        return None
    return DecompositionNode(
        kind="swap",
        shape=normalize_code(code),
        detail=f"angle={witness.angle};left={witness.left_half_bits};right={witness.right_half_bits}",
    )


def bitmask_swap_tree(code: str) -> DecompositionNode | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    swap_status = bitmask_swap_impossibility(normalized)
    if swap_status == "swap_both_blocked":
        return None
    return DecompositionNode(
        kind="swap",
        shape=normalized,
        detail="bitmask_" + normalize_code_label(swap_status or "swapable"),
    )


def layer_removal_tree(code: str) -> DecompositionNode | None:
    normalized = normalize_code(code)
    removed_count, removed_crystal, final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    if removed_count <= 0 or removed_crystal:
        return None

    current = normalized
    peeled_layers: list[str] = []
    for _ in range(removed_count):
        current, removed = bitmask_remove_top_nonempty_layer(current)
        if removed is None:
            return None
        peeled_layers.append(removed)

    base = bitmask_swap_tree(current)
    if base is None:
        return None

    children: list[DecompositionNode] = [base]
    children.extend(
        stack_input_tree(layer, f"peeled_top_{index + 1}")
        for index, layer in enumerate(reversed(peeled_layers))
    )
    return DecompositionNode(
        kind="stack",
        shape=normalized,
        detail=f"layer_removal_{removed_count}_{normalize_code_label(final_swap or 'swapable')}",
        children=tuple(children),
    )


def reference_decomposition_tree(code: str, layers: int) -> DecompositionNode | None:
    normalized = normalize_code(code)
    if not normalized:
        return DecompositionNode(kind="empty", shape="", detail="empty_shape")
    claw_seed = claw_tail_seed_tree(code)
    if claw_seed is not None:
        return claw_seed
    pp_inverse = pp_inverse_predecessor_tree(code, layers)
    if pp_inverse is not None:
        return pp_inverse
    claw_verified = claw_verified_tree(code, layers)
    if claw_verified is not None:
        return claw_verified
    swap = swappability_tree(code, layers)
    if swap is not None:
        return swap
    bitmask_swap = bitmask_swap_tree(code)
    if bitmask_swap is not None:
        return bitmask_swap
    peeled = layer_removal_tree(code)
    if peeled is not None:
        return peeled
    half_empty_stack = half_empty_stackability_tree(code)
    if half_empty_stack is not None:
        return half_empty_stack
    small_right = small_right_cminusss_tree(code)
    if small_right is not None:
        return small_right
    dense_s_support = small_right_dense_s_support_tree(code)
    if dense_s_support is not None:
        return dense_s_support
    pp_stackability = small_right_pp_stackability_tree(code)
    if pp_stackability is not None:
        return pp_stackability
    top_sss_tail = top_sss_tail_stack_tree(code)
    if top_sss_tail is not None:
        return top_sss_tail
    top_sss_right_crystal_pair = top_sss_right_crystal_pair_support_tree(code)
    if top_sss_right_crystal_pair is not None:
        return top_sss_right_crystal_pair
    top_sss_center_crystal_pair = top_sss_center_crystal_pair_support_tree(code)
    if top_sss_center_crystal_pair is not None:
        return top_sss_center_crystal_pair
    top_sss_center_three_layer = top_sss_center_three_layer_support_tree(code)
    if top_sss_center_three_layer is not None:
        return top_sss_center_three_layer
    small_right_stair_support = small_right_stair_s_support_tree(code)
    if small_right_stair_support is not None:
        return small_right_stair_support
    small_right_midpin_support = small_right_midpin_s_support_tree(code)
    if small_right_midpin_support is not None:
        return small_right_midpin_support
    low_base_s_support = small_right_low_base_s_support_tree(code)
    if low_base_s_support is not None:
        return low_base_s_support
    pp_low_base_support = small_right_pp_low_base_support_tree(code)
    if pp_low_base_support is not None:
        return pp_low_base_support
    paired_s_support = paired_small_right_s_support_tree(code)
    if paired_s_support is not None:
        return paired_s_support
    shallow_left_s_support = small_right_shallow_left_s_support_tree(code)
    if shallow_left_s_support is not None:
        return shallow_left_s_support
    mid_stack_low_frontier = mid_stack_delta_low_frontier_support_tree(code)
    if mid_stack_low_frontier is not None:
        return mid_stack_low_frontier
    top_pp_support = top_pp_pin_predecessor_support_tree(code)
    if top_pp_support is not None:
        return top_pp_support
    stack = stackability_tree(code, layers)
    if stack is not None:
        return stack
    verdict = reference_cpcp_verdict(code, layers)
    if verdict is not None and verdict[0] == "possible":
        return pp_trace_tree(code, layers)
    hybrid = hybrid_rescue_tree(code)
    if hybrid is not None:
        return hybrid
    return None


def audited_reference_decomposition_tree(code: str, layers: int) -> DecompositionNode | None:
    snapshots = (
        HYBRID_RESCUE_STATS.copy(),
        HYBRID_RESCUE_TIMES.copy(),
        CLAW_VERIFY_STATS.copy(),
        CLAW_VERIFY_TIMES.copy(),
        PP_INVERSE_STATS.copy(),
    )
    try:
        return reference_decomposition_tree(code, layers)
    finally:
        for target, snapshot in zip(
            (
                HYBRID_RESCUE_STATS,
                HYBRID_RESCUE_TIMES,
                CLAW_VERIFY_STATS,
                CLAW_VERIFY_TIMES,
                PP_INVERSE_STATS,
            ),
            snapshots,
        ):
            target.clear()
            target.update(snapshot)


PROCESSED_CLAW_IMPOSSIBLE_PILLAR_PATTERNS = (
    re.compile(r"-P"),
    re.compile(r"^P*-+c"),
    re.compile(r"[^P]P.*c"),
    re.compile(r"c-.*c"),
    re.compile(r"c.-+c"),
    re.compile(r"^S*-?S*c(.*c)?(S-+)+c"),
)


def processed_claw_fast_reject_reason(code: str) -> str | None:
    normalized = normalize_code(code)
    if not normalized or "c" not in normalized:
        return "no_c"
    layers = normalized.split(":")
    pillars = ["".join(layer[q] for layer in layers) for q in range(4)]
    nonempty = [idx for idx, pillar in enumerate(pillars) if pillar.strip("-")]
    if len(nonempty) == 1 and nonempty[0] == 0 and len(layers) != 1:
        return "q1_corner_branch"
    if not bitmask_physics_stable(normalized):
        return "unstable"
    for pillar in pillars:
        if any(pattern.search(pillar) for pattern in PROCESSED_CLAW_IMPOSSIBLE_PILLAR_PATTERNS):
            return "impossible_pattern"
    removed_count, _removed_crystal, _final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    if removed_count != 0:
        return "layer_removed"
    return None


@lru_cache(maxsize=100_000)
def claw_primitive_swapable_predecessor(code: str) -> str | None:
    normalized = normalize_code(code)
    if not normalized:
        return None
    parts = normalized.split(":")
    if len(parts) < 2:
        return None
    removal = bitmask_layer_removal_context(normalized)[:3]
    if (parts[-1], parts[-2], removal) not in CLAW_PRIMITIVE_PREDECESSOR_TOP_PEN_REMS:
        return None
    layers = len(normalized.split(":"))
    for predecessor_family in (bitmask_inverse_push_pin_candidates, bitmask_bridge_inverse_push_pin_candidates):
        for predecessor in predecessor_family(normalized, layers):
            if bitmask_push_pin(predecessor, max(MAX_LAYERS, layers)) != normalized:
                continue
            if processed_claw_fast_reject_reason(predecessor) is not None:
                continue
            if bitmask_swap_impossibility(predecessor) is None:
                return predecessor
    return None


@lru_cache(maxsize=100_000)
def claw_verify_status(code: str) -> tuple[bool, str]:
    normalized = normalize_code(code)
    removed_count, removed_crystal, _final_swap, _base_depth = bitmask_layer_removal_context(normalized)
    if removed_count <= 0 or not removed_crystal:
        return False, "not_claw_context"
    CLAW_VERIFY_STATS["calls"] += 1
    tick = time.perf_counter()
    primitive_predecessor = claw_primitive_swapable_predecessor(normalized)
    CLAW_VERIFY_TIMES["primitive_predecessor"] += time.perf_counter() - tick
    if primitive_predecessor is not None:
        CLAW_VERIFY_STATS["primitive_predecessor_verified"] += 1
        return True, "claw_possible"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape
            from shape_classifier import ClassificationReason, ShapeType, analyze_shape
            from claw_tracer import claw_process
            from data_operations import simplify_shape

            shape_repr = repr(Shape.from_string(normalized))
            tick = time.perf_counter()
            processed_shape_str = claw_process(shape_repr)
            CLAW_VERIFY_TIMES["claw_process"] += time.perf_counter() - tick
            processed_code = simplify_shape(processed_shape_str) if processed_shape_str else ""
            tick = time.perf_counter()
            if bitmask_push_pin(processed_code, max(MAX_LAYERS, len(normalized.split(":")))) != normalized:
                CLAW_VERIFY_TIMES["push_pin"] += time.perf_counter() - tick
                CLAW_VERIFY_STATS["pin_mismatch"] += 1
                return False, ClassificationReason.REASON_CLAW_IMPOSSIBLE
            CLAW_VERIFY_TIMES["push_pin"] += time.perf_counter() - tick
            tick = time.perf_counter()
            reject_reason = processed_claw_fast_reject_reason(processed_code)
            if reject_reason is not None:
                CLAW_VERIFY_TIMES["classify_processed"] += time.perf_counter() - tick
                CLAW_VERIFY_STATS["fast_reject_" + reject_reason] += 1
                CLAW_VERIFY_STATS["swap_impossible"] += 1
                return False, ClassificationReason.REASON_CLAW_SWAP_IMPOSSIBLE
            processed_shape = Shape.from_string(processed_shape_str)
            classification_type, _classification_reason = cached_skip_shape_analysis(repr(processed_shape))
            CLAW_VERIFY_TIMES["classify_processed"] += time.perf_counter() - tick
            if ShapeType.SWAPABLE.value not in classification_type:
                CLAW_VERIFY_STATS["swap_impossible"] += 1
                return False, ClassificationReason.REASON_CLAW_SWAP_IMPOSSIBLE
            CLAW_VERIFY_STATS["verified"] += 1
            verified, reason = True, ClassificationReason.REASON_CLAW_POSSIBLE
    except Exception:
        CLAW_VERIFY_STATS["error"] += 1
        verified, reason = False, "error"
    return verified, reason


def claw_verify_core_verdict(code: str) -> tuple[str, str] | None:
    verified, _reason = claw_verify_status(code)
    if verified:
        return "possible", "kernel_claw_verified"
    return None


def claw_failure_core_verdict(code: str) -> tuple[str, str] | None:
    verified, reason = claw_verify_status(code)
    if reason == "not_claw_context":
        return None
    if verified:
        return None
    return "impossible", "kernel_claw_verification_failed_" + normalize_code_label(reason)


def _rotate_layer_text(layer: str, turns: int) -> str:
    turns %= 4
    if turns == 0:
        return layer
    out = ["-"] * 4
    for q, ch in enumerate(layer):
        out[(q + turns) % 4] = ch
    return "".join(out)


def _rotate_code_text(code: str, turns: int) -> str:
    return ":".join(_rotate_layer_text(layer, turns) for layer in normalize_code(code).split(":") if layer)


def _claw_hybrid_rotated_code(code: str) -> str | None:
    result = _claw_hybrid_rotated_code_and_restore_turns(code)
    return result[0] if result else None


def _claw_hybrid_rotated_code_and_restore_turns(code: str) -> tuple[str, int] | None:
    normalized = normalize_code(code)
    if not normalized or "c" not in normalized:
        return None
    layers = normalized.split(":")
    highest_q = -1
    for layer in reversed(layers):
        for q, ch in enumerate(layer):
            if ch == "c":
                highest_q = q
                break
        if highest_q >= 0:
            break
    if highest_q == 1:
        return _rotate_code_text(normalized, -1), 1
    if highest_q == 2:
        return _rotate_code_text(normalized, 2), 2
    if highest_q == 3:
        return _rotate_code_text(normalized, 1), -1
    return normalized, 0


def _adjust_claw_hybrid_pattern(pattern_key: str, layer_count: int) -> str:
    if layer_count <= 4:
        layers_to_remove = 5 - layer_count
        pattern_segments = pattern_key.split(":")
        return ":".join(pattern_segments[:-layers_to_remove]) if layers_to_remove > 0 else pattern_key
    return pattern_key


@lru_cache(maxsize=16)
def _compiled_claw_hybrid_patterns(layer_count: int) -> tuple[re.Pattern[str], ...]:
    from claw_hybrid_tracer import HYBRID_PATTERNS

    return tuple(re.compile(_adjust_claw_hybrid_pattern(pattern_key, layer_count)) for pattern_key in HYBRID_PATTERNS)


@lru_cache(maxsize=100_000)
def claw_hybrid_pattern_possible(code: str) -> bool:
    rotated = _claw_hybrid_rotated_code(code)
    if not rotated:
        return False
    layer_count = len(rotated.split(":"))
    try:
        patterns = _compiled_claw_hybrid_patterns(layer_count)
    except Exception:
        return True
    for pattern in patterns:
        if pattern.fullmatch(rotated):
            return True
    return False


@lru_cache(maxsize=100_000)
def basic_hybrid_has_b_candidate(code: str) -> bool:
    normalized = normalize_code(code)
    if not normalized or "c" not in normalized:
        return False
    layers = normalized.split(":")
    for q in range(4):
        highest_c = -1
        for l in range(len(layers) - 1, -1, -1):
            if layers[l][q] == "c":
                highest_c = l
                break
        if highest_c >= 0:
            for l in range(highest_c + 1, len(layers)):
                if layers[l][q] != "-":
                    return True
        else:
            for layer in layers:
                if layer[q] != "-":
                    return True
    return False


def _hybrid_stack_rescue_attempt(shape_obj: object, claw_mode: bool, normalized: str) -> tuple[HybridRescueWitness | None, str]:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape
            from shape_classifier import ShapeType, analyze_shape
            from data_operations import simplify_shape

            if claw_mode:
                if not claw_hybrid_pattern_possible(normalized):
                    HYBRID_RESCUE_STATS["claw_reject_pattern"] += 1
                    return None, "pattern_reject"
                parts = normalized.split(":")
                removal = bitmask_layer_removal_context(normalized)[:3]
                if (
                    len(parts) >= 2
                    and (parts[-1], parts[-2], removal) in CLAW_HYBRID_MISS_ONLY_TOP_PEN_REMS
                ):
                    HYBRID_RESCUE_STATS["claw_reject_miss_only"] += 1
                    return None, "miss_only_reject"
                from claw_hybrid_tracer import claw_hybrid

                HYBRID_RESCUE_STATS["claw_exec"] += 1
                output_a, output_b = claw_hybrid(shape_obj.copy())
            else:
                if not basic_hybrid_has_b_candidate(normalized):
                    HYBRID_RESCUE_STATS["basic_reject_initial_empty_b"] += 1
                    return None, "initial_empty_b"
                parts = normalized.split(":")
                removal = bitmask_layer_removal_context(normalized)[:3]
                if (
                    len(parts) >= 2
                    and (parts[-1], parts[-2], removal) in BASIC_HYBRID_MISS_ONLY_TOP_PEN_REMS
                ):
                    HYBRID_RESCUE_STATS["basic_reject_miss_only"] += 1
                    return None, "miss_only_reject"
                HYBRID_RESCUE_STATS["basic_exec"] += 1
                output_a, output_b = shape_obj.copy().hybrid()

            b_repr = repr(output_b)
            if not b_repr:
                HYBRID_RESCUE_STATS[("claw" if claw_mode else "basic") + "_fail_empty_b"] += 1
                return None, "empty_b"
            left_code = normalize_code(simplify_shape(repr(output_a)))
            right_code = normalize_code(simplify_shape(b_repr))
            removed_count, removed_crystal, final_swap, _base_depth = bitmask_layer_removal_context(left_code)
            a_type, _a_reason = cached_skip_shape_analysis(repr(output_a))
            if a_type == ShapeType.IMPOSSIBLE.value:
                HYBRID_RESCUE_STATS[("claw" if claw_mode else "basic") + "_fail_a_impossible"] += 1
                return None, "a_impossible"
            replayed = bitmask_stack(
                left_code,
                right_code,
                max_layers=max(MAX_LAYERS, len(normalized.split(":"))),
            )
            if replayed != normalized:
                HYBRID_RESCUE_STATS[("claw" if claw_mode else "basic") + "_fail_stack_miss"] += 1
                return None, "stack_miss"
            return (
                HybridRescueWitness(
                    mode="claw" if claw_mode else "basic",
                    left=left_code,
                    right=right_code,
                ),
                "hit",
            )
    except Exception:
        HYBRID_RESCUE_STATS[("claw" if claw_mode else "basic") + "_error"] += 1
        return None, "error"


@lru_cache(maxsize=100_000)
def hybrid_rescue_core_verdict(code: str) -> tuple[str, str] | None:
    normalized = normalize_code(code)
    if not normalized or "c" not in normalized:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape

            shape_obj = Shape.from_string(normalized)
    except Exception:
        return None
    tick = time.perf_counter()
    HYBRID_RESCUE_STATS["claw_calls"] += 1
    claw_witness, claw_reason = _hybrid_stack_rescue_attempt(shape_obj, claw_mode=True, normalized=normalized)
    if claw_witness is not None:
        HYBRID_RESCUE_TIMES["claw"] += time.perf_counter() - tick
        HYBRID_RESCUE_STATS["claw_hits"] += 1
        return "possible", "kernel_claw_complex_hybrid_rescue"
    HYBRID_RESCUE_TIMES["claw"] += time.perf_counter() - tick
    tick = time.perf_counter()
    HYBRID_RESCUE_STATS["basic_calls"] += 1
    if _hybrid_stack_rescue_attempt(shape_obj, claw_mode=False, normalized=normalized)[0] is not None:
        HYBRID_RESCUE_TIMES["basic"] += time.perf_counter() - tick
        HYBRID_RESCUE_STATS["basic_hits"] += 1
        return "possible", "kernel_complex_hybrid_rescue"
    HYBRID_RESCUE_TIMES["basic"] += time.perf_counter() - tick
    return None


def hybrid_rescue_witness(code: str) -> HybridRescueWitness | None:
    normalized = normalize_code(code)
    if not normalized or "c" not in normalized:
        return None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape

            shape_obj = Shape.from_string(normalized)
    except Exception:
        return None
    claw, claw_reason = _hybrid_stack_rescue_attempt(shape_obj, claw_mode=True, normalized=normalized)
    if claw is not None:
        return claw
    return _hybrid_stack_rescue_attempt(shape_obj, claw_mode=False, normalized=normalized)[0]


def hybrid_rescue_skip_reason(code: str) -> str | None:
    normalized = normalize_code(code)
    parts = normalized.split(":") if normalized else []
    if not parts:
        return None
    removal = bitmask_layer_removal_context(normalized)[:3]
    if (
        (parts[-1], removal) in TOP_LAYER_HYBRID_MISS_ONLY
        and basic_hybrid_has_b_candidate(normalized)
        and claw_hybrid_pattern_possible(normalized)
    ):
        return "top_layer_hybrid_miss_only_strip"
    if parts[-1] == "c--S" and removal == (1, True, "swap_14_23_blocked"):
        return "top_cminus_s_swap14_blocked_single_crystal_strip"
    if (
        len(parts) >= 2
        and parts[-1] == "cSSS"
        and parts[-2] == "-PS-"
        and removal == (1, True, "swap_12_34_blocked")
    ):
        return "top_csss_penult_ps_swap12_blocked_single_crystal_strip"
    if (
        len(parts) >= 2
        and parts[-1] == "cSSS"
        and parts[-2] == "-SS-"
        and removal == (1, True, "swap_12_34_blocked")
    ):
        return "top_csss_penult_ss_swap12_blocked_single_crystal_strip"
    if (
        len(parts) >= 2
        and parts[-1] == "cS--"
        and parts[-2] == "S-Sc"
        and removal == (1, True, "swap_12_34_blocked")
    ):
        return "top_csminus_penult_s_sc_swap12_blocked_single_crystal_strip"
    return None


def hybrid_rescue_tree(code: str) -> DecompositionNode | None:
    witness = hybrid_rescue_witness(code)
    if witness is None:
        return None
    layers = len(normalize_code(code).split(":"))
    return DecompositionNode(
        kind="stack",
        shape=normalize_code(code),
        detail=f"{witness.mode}_hybrid_rescue",
        children=(
            verified_left_predecessor_tree(witness.left, layers, f"{witness.mode}_hybrid_left"),
            stack_input_tree(witness.right, f"{witness.mode}_hybrid_right"),
        ),
    )


def normalize_code_label(text: str) -> str:
    label = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return label[:80] if label else "empty"


def legacy_verdict(code: str) -> tuple[str, str, str, str]:
    with contextlib.redirect_stdout(io.StringIO()):
        from shape_classifier import ShapeType, analyze_shape

        cls, reason = analyze_shape(code)
    if cls == ShapeType.UNKNOWN.value:
        legacy = "unknown"
    elif cls == ShapeType.IMPOSSIBLE.value:
        legacy = "impossible"
    else:
        legacy = "possible"
    if "analyzer.virtual" in reason or "Virtual" in reason or "가상" in reason:
        strict = "impossible"
    elif legacy == "impossible" and "Simple Corner" in reason:
        strict = "possible"
    else:
        strict = legacy
    return legacy, strict, cls, reason


def legacy_hint_signature(code: str) -> str:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from shape import Shape
            from shape_classifier import (
                ClassificationReason,
                ShapeType,
                analyze_shape,
                _check_swap_impossibility,
                _perform_layer_removal_loop,
                check_physics_stability,
            )
            from claw_hybrid_tracer import claw_hybrid

            shape_obj = Shape.from_string(code)
            stable = check_physics_stability(shape_obj)
            initial_swap = _check_swap_impossibility(shape_obj)
            removed_layers, removed_count, final_swap, base_shape = _perform_layer_removal_loop(shape_obj.copy())

            def split_witness(split_name: str, a_obj, b_obj) -> str:
                a_repr = repr(a_obj)
                b_repr = repr(b_obj)
                if not b_repr:
                    return f"{split_name}:emptyB"
                a_type, _ = cached_skip_shape_analysis(a_repr)
                a_ok = a_type not in (ShapeType.IMPOSSIBLE.value, ShapeType.UNKNOWN.value)
                stack_ab = repr(Shape.stack(a_obj, b_obj)) == repr(shape_obj)
                stack_ba = repr(Shape.stack(b_obj, a_obj)) == repr(shape_obj)
                return (
                    f"{split_name}:a{int(a_ok)}s{int(stack_ab or stack_ba)}"
                    f"ab{int(stack_ab)}ba{int(stack_ba)}L{len(a_obj.layers)}/{len(b_obj.layers)}"
                    f"Bp{int('P' in b_repr)}c{int('c' in b_repr)}"
                )

            try:
                basic_a, basic_b = shape_obj.copy().hybrid()
                hybrid_hint = split_witness("hy", basic_a, basic_b)
            except Exception as exc:
                hybrid_hint = f"hy:error:{type(exc).__name__}"
            try:
                claw_a, claw_b = claw_hybrid(shape_obj.copy())
                claw_hybrid_hint = split_witness("chy", claw_a, claw_b)
            except Exception as exc:
                claw_hybrid_hint = f"chy:error:{type(exc).__name__}"
    except Exception as exc:
        return f"hint_error:{type(exc).__name__}"

    initial_bucket = (
        "swap_both_blocked"
        if initial_swap == ClassificationReason.REASON_SWAP_IMPOSSIBLE
        else "swap_one_blocked"
        if initial_swap
        else "swapable"
    )
    final_bucket = (
        "base_both_blocked"
        if final_swap == ClassificationReason.REASON_SWAP_IMPOSSIBLE
        else "base_one_blocked"
        if final_swap
        else "base_swapable"
    )
    removed_c = any("c" in layer for layer in removed_layers)
    first = normalize_code(code).split(":")[0] if normalize_code(code) else "----"
    bottom = f"bP{first.count('P')}S{first.count('S')}c{int('c' in first)}"
    base_depth = len(base_shape.layers) if base_shape is not None else 0
    stable_tag = "stable" if stable else "unstable"
    return (
        f"{stable_tag}|{initial_bucket}|strip{removed_count}c{int(removed_c)}|"
        f"{final_bucket}|base{base_depth}|{bottom}|{hybrid_hint}|{claw_hybrid_hint}"
    )


def projected_legacy_hint_features(signature: str) -> tuple[str, ...]:
    if signature.startswith("hint_error:"):
        return (signature,)
    parts = signature.split("|")
    features = list(parts[:6])
    for part in parts[6:]:
        split_name = part.split(":", 1)[0]
        if ":error:" in part or part.endswith(":emptyB"):
            features.append(part)
            continue
        match = re.search(r":a([01])s([01])ab([01])ba([01])L(\d+)/(\d+)Bp([01])c([01])", part)
        if not match:
            features.append(part)
            continue
        a_ok, stacks, stack_ab, stack_ba, _a_layers, b_layers, b_has_p, b_has_c = match.groups()
        features.extend(
            (
                f"{split_name}:a{a_ok}",
                f"{split_name}:s{stacks}",
                f"{split_name}:ab{stack_ab}",
                f"{split_name}:ba{stack_ba}",
                f"{split_name}:Bp{b_has_p}",
                f"{split_name}:Bc{b_has_c}",
                f"{split_name}:BL{b_layers}",
            )
        )
    return tuple(features)


def reference_mismatch_tag(symbolic_verdict: str, symbolic_bucket: str, reference_verdict: str) -> str:
    if "single_column_corner" in symbolic_bucket:
        return "single_column_policy"
    if symbolic_verdict == "impossible" and reference_verdict == "possible":
        if "claw_verification_failed" in symbolic_bucket or "corner" in symbolic_bucket:
            return "strict_impossible_vs_cpcp_possible"
        return "symbolic_impossible_reference_possible"
    if symbolic_verdict == "possible" and reference_verdict == "impossible":
        if symbolic_bucket.startswith("possible_"):
            return "symbolic_frontier_positive_not_in_cpcp"
        return "kernel_positive_not_in_cpcp"
    return "structural_reference_mismatch"


def run_eval(args: argparse.Namespace, corner_mode: str) -> int:
    HYBRID_RESCUE_STATS.clear()
    HYBRID_RESCUE_TIMES.clear()
    CLAW_VERIFY_STATS.clear()
    CLAW_VERIFY_TIMES.clear()
    PP_INVERSE_STATS.clear()
    automaton = SymbolicFrontierAutomaton(
        corner_mode=corner_mode,
        max_depth=args.depth,
        rotate_canonical=False,
        experiments=frozenset(args.experiment),
    )
    if args.eval_random:
        code_iter = iter_random_codes(args.eval_random, args.eval_random_layers, args.seed)
    elif args.eval_per_file:
        code_iter = iter_data_codes_by_file(args.eval_data, args.eval_per_file, args.seed, not args.no_eval_shuffle, args.depth)
    else:
        code_iter = iter_data_codes(args.eval_data, args.depth)

    total = skipped_by_layer = skipped_by_bucket = non_unknown = fallback_used = kernel_used = legacy_fallback_used = legacy_match = strict_match = virtual_legacy_possible = 0
    decomposition_tree_checked = decomposition_tree_missing = 0
    decomposition_tree_open_leaf_total = decomposition_tree_open_tree_count = 0
    compare_total = compare_non_unknown = 0
    legacy_compare_known = reference_compare_known = legacy_known_match = strict_known_match = reference_known_match = 0
    reference_match = 0
    symbolic_time = kernel_time = legacy_time = reference_time = 0.0
    kernel_step_times: Counter[str] = Counter()
    buckets: Counter[tuple[str, str]] = Counter()
    legacy_pairs: Counter[tuple[str, str, str]] = Counter()
    strict_pairs: Counter[tuple[str, str, str]] = Counter()
    reference_pairs: Counter[tuple[str, str, str]] = Counter()
    reference_mismatch_tags: Counter[str] = Counter()
    legacy_hints: Counter[tuple[str, str, str]] = Counter()
    legacy_hint_features: Counter[tuple[str, str, str]] = Counter()
    layer_counts: Counter[int] = Counter()
    kernel_step_counts: Counter[str] = Counter()
    decomposition_tree_roots: Counter[str] = Counter()
    decomposition_tree_dependencies: Counter[tuple[str, ...]] = Counter()
    decomposition_tree_open_leaf_kinds: Counter[str] = Counter()
    bucket_samples: dict[tuple[str, str], list[str]] = {}
    samples: list[str] = []
    legacy_unknown_samples: list[str] = []
    strict_samples: list[str] = []
    reference_samples: list[str] = []
    decomposition_tree_samples: list[str] = []
    started = time.perf_counter()
    compare_every = max(1, args.compare_every)
    selected_compare_mode = "none" if args.no_compare_legacy else args.compare_against
    skip_bucket_re = re.compile(args.eval_skip_bucket_regex) if args.eval_skip_bucket_regex else None

    for code in code_iter:
        if args.eval_limit and total >= args.eval_limit:
            break
        if args.eval_max_seconds and time.perf_counter() - started >= args.eval_max_seconds:
            break
        normalized_for_count = normalize_code(code)
        normalized_layer_count = len(normalized_for_count.split(":")) if normalized_for_count else 0
        if args.eval_min_layers and normalized_layer_count < args.eval_min_layers:
            skipped_by_layer += 1
            continue
        if args.eval_max_layers and normalized_layer_count > args.eval_max_layers:
            skipped_by_layer += 1
            continue
        total += 1
        if "reference-cpcp" in args.experiment:
            tick = time.perf_counter()
            reference_kernel = reference_cpcp_verdict(code, args.depth)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["reference_cpcp"] += elapsed
            kernel_step_counts["reference_cpcp"] += 1
            if reference_kernel is not None:
                sv, sb = reference_kernel
                fallback_used += 1
                kernel_used += 1
            else:
                tick = time.perf_counter()
                sv, sb = symbolic_verdict(automaton, code, args.depth)
                symbolic_time += time.perf_counter() - tick
        else:
            tick = time.perf_counter()
            sv, sb = symbolic_verdict(automaton, code, args.depth)
            symbolic_time += time.perf_counter() - tick
        if sv == "unknown" and "reference-derived-positive" in args.experiment and args.depth <= 4:
            tick = time.perf_counter()
            positive = None
            if reference_cpcp_swappable_verdict(code, args.depth) is not None:
                positive = ("possible", "reference_derived_swappable")
            elif reference_stackability_core_verdict(code, args.depth) is not None:
                positive = ("possible", "reference_derived_stackable")
            else:
                subtype = pp_subtype_candidate(code, args.depth)
                if subtype.subtype in REFERENCE_DERIVED_PP_POSITIVE_SUBTYPES:
                    ref = reference_cpcp_verdict(code, args.depth)
                    if ref is not None and ref[0] == "possible":
                        positive = ("possible", f"reference_derived_{subtype.subtype}")
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["reference_derived_positive"] += elapsed
            kernel_step_counts["reference_derived_positive"] += 1
            if positive is not None:
                sv, sb = positive
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback in ("physics-core", "swap-core", "kernel-core", "kernel-hybrid-core"):
            tick = time.perf_counter()
            kernel = physics_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["physics"] += elapsed
            kernel_step_counts["physics"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core" and "reference-cpcp" in args.experiment:
            tick = time.perf_counter()
            normalized_depth = len(normalize_code(code).split(":")) if normalize_code(code) else 0
            kernel = reference_cpcp_verdict(code, args.depth) if normalized_depth <= args.depth else None
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["reference_cpcp"] += elapsed
            kernel_step_counts["reference_cpcp"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback in ("swap-core", "kernel-core", "kernel-hybrid-core") and "defer-swap-positive" not in args.experiment:
            tick = time.perf_counter()
            kernel = swap_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["swap"] += elapsed
            kernel_step_counts["swap"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback in ("kernel-core", "kernel-hybrid-core") and "defer-swap-positive" not in args.experiment:
            tick = time.perf_counter()
            kernel = layer_removal_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["layer_removal"] += elapsed
            kernel_step_counts["layer_removal"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = claw_tail_seed_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["claw_tail_seed"] += elapsed
            kernel_step_counts["claw_tail_seed"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = pp_inverse_predecessor_core_verdict(code, args.depth)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["pp_inverse_predecessor"] += elapsed
            kernel_step_counts["pp_inverse_predecessor"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core" and "zero-stack-pp-predecessor-core" in args.experiment:
            tick = time.perf_counter()
            kernel = zero_stack_pp_predecessor_core_verdict(code, args.depth)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["zero_stack_pp_predecessor"] += elapsed
            kernel_step_counts["zero_stack_pp_predecessor"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core" and "stackability-swap12-core" in args.experiment:
            tick = time.perf_counter()
            kernel = stackability_swap12_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["stackability_swap12"] += elapsed
            kernel_step_counts["stackability_swap12"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = stackability_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["stackability"] += elapsed
            kernel_step_counts["stackability"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = half_empty_stackability_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["half_empty_stackability"] += elapsed
            kernel_step_counts["half_empty_stackability"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_cminusss_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_cminusss"] += elapsed
            kernel_step_counts["small_right_cminusss"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_dense_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_dense_s_support"] += elapsed
            kernel_step_counts["small_right_dense_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_pp_stackability_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_pp_stackability"] += elapsed
            kernel_step_counts["small_right_pp_stackability"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = top_sss_tail_stack_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["top_sss_tail_stack"] += elapsed
            kernel_step_counts["top_sss_tail_stack"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = top_sss_right_crystal_pair_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["top_sss_right_crystal_pair_support"] += elapsed
            kernel_step_counts["top_sss_right_crystal_pair_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = top_sss_center_crystal_pair_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["top_sss_center_crystal_pair_support"] += elapsed
            kernel_step_counts["top_sss_center_crystal_pair_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = top_sss_center_three_layer_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["top_sss_center_three_layer_support"] += elapsed
            kernel_step_counts["top_sss_center_three_layer_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_stair_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_stair_s_support"] += elapsed
            kernel_step_counts["small_right_stair_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_midpin_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_midpin_s_support"] += elapsed
            kernel_step_counts["small_right_midpin_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_low_base_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_low_base_s_support"] += elapsed
            kernel_step_counts["small_right_low_base_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_pp_low_base_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_pp_low_base_support"] += elapsed
            kernel_step_counts["small_right_pp_low_base_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = paired_small_right_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["paired_small_right_s_support"] += elapsed
            kernel_step_counts["paired_small_right_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = small_right_shallow_left_s_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["small_right_shallow_left_s_support"] += elapsed
            kernel_step_counts["small_right_shallow_left_s_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = mid_stack_delta_low_frontier_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["mid_stack_delta_low_frontier_support"] += elapsed
            kernel_step_counts["mid_stack_delta_low_frontier_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = top_pp_pin_predecessor_support_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["top_pp_pin_predecessor_support"] += elapsed
            kernel_step_counts["top_pp_pin_predecessor_support"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if (
            sv == "unknown"
            and args.depth <= 4
            and args.fallback == "kernel-hybrid-core"
            and "reference-stackability-core" in args.experiment
        ):
            tick = time.perf_counter()
            kernel = reference_stackability_core_verdict(code, args.depth)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["reference_stackability"] += elapsed
            kernel_step_counts["reference_stackability"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if (
            sv == "unknown"
            and args.fallback in ("kernel-core", "kernel-hybrid-core")
            and (
                args.fallback != "kernel-hybrid-core"
                or claw_bottom_floor_reject_core_verdict(code) is None
            )
        ):
            tick = time.perf_counter()
            kernel = claw_verify_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["claw_verify"] += elapsed
            kernel_step_counts["claw_verify"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            skip_reason = hybrid_rescue_skip_reason(code)
            if skip_reason is not None:
                HYBRID_RESCUE_STATS["prefilter_skip_" + skip_reason] += 1
            else:
                tick = time.perf_counter()
                kernel = hybrid_rescue_core_verdict(code)
                elapsed = time.perf_counter() - tick
                kernel_time += elapsed
                kernel_step_times["hybrid_rescue"] += elapsed
                kernel_step_counts["hybrid_rescue"] += 1
                if kernel is not None:
                    sv, sb = kernel
                    fallback_used += 1
                    kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = claw_bottom_floor_reject_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["claw_bottom_floor_reject"] += elapsed
            kernel_step_counts["claw_bottom_floor_reject"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if sv == "unknown" and args.fallback == "kernel-hybrid-core":
            tick = time.perf_counter()
            kernel = claw_failure_core_verdict(code)
            elapsed = time.perf_counter() - tick
            kernel_time += elapsed
            kernel_step_times["claw_failure"] += elapsed
            kernel_step_counts["claw_failure"] += 1
            if kernel is not None:
                sv, sb = kernel
                fallback_used += 1
                kernel_used += 1
        if skip_bucket_re and skip_bucket_re.search(f"{sv}/{sb}"):
            total -= 1
            skipped_by_bucket += 1
            continue
        if args.fail_on_missing_decomposition_tree and sv == "possible":
            decomposition_tree_checked += 1
            tree = audited_reference_decomposition_tree(code, args.depth)
            if tree is None:
                decomposition_tree_missing += 1
                if len(decomposition_tree_samples) < args.max_mismatches:
                    decomposition_tree_samples.append(
                        f"{normalize_code(code)}\tmissing_decomposition_tree\tbucket={sv}/{sb}"
                )
            else:
                decomposition_tree_roots[decomposition_tree_root_key(tree)] += 1
                decomposition_tree_dependencies[decomposition_tree_dependency_tags(tree)] += 1
                open_leaves = decomposition_tree_open_leaf_keys(tree)
                if open_leaves:
                    decomposition_tree_open_tree_count += 1
                    decomposition_tree_open_leaf_total += open_leaves.total()
                    decomposition_tree_open_leaf_kinds.update(open_leaves)
        layer_counts[normalized_layer_count] += 1
        lv = strict = lc = lr = ref_verdict = ref_bucket = ""
        needs_legacy_fallback = sv == "unknown" and args.fallback in ("legacy-core", "kernel-core", "kernel-hybrid-core")
        compare_mode = selected_compare_mode
        compare_enabled = compare_mode != "none"
        if compare_enabled and compare_every > 1 and total % compare_every != 0:
            compare_enabled = False
        if compare_enabled and args.compare_limit and compare_total >= args.compare_limit:
            compare_enabled = False
        compare_legacy_enabled = compare_enabled and compare_mode in ("legacy", "both")
        compare_reference_enabled = compare_enabled and compare_mode in ("reference", "both")
        if compare_enabled:
            compare_total += 1
        if needs_legacy_fallback or compare_legacy_enabled:
            tick = time.perf_counter()
            lv, strict, lc, lr = legacy_verdict(code)
            legacy_time += time.perf_counter() - tick
        if compare_reference_enabled:
            tick = time.perf_counter()
            reference = reference_cpcp_verdict(code, args.depth)
            reference_time += time.perf_counter() - tick
            if reference is None:
                ref_verdict, ref_bucket = "unknown", "reference_cpcp_unavailable"
            else:
                ref_verdict, ref_bucket = reference
        if needs_legacy_fallback:
            sv, sb = strict_legacy_parts_to_symbolic(strict, lc, lr)
            fallback_used += 1
            legacy_fallback_used += 1
        buckets[(sv, sb)] += 1
        if args.bucket_samples:
            sample_key = (sv, sb)
            samples_for_bucket = bucket_samples.setdefault(sample_key, [])
            if len(samples_for_bucket) < args.bucket_samples:
                samples_for_bucket.append(normalized_for_count)
        if compare_legacy_enabled:
            legacy_pairs[(sv, lv, sb)] += 1
            strict_pairs[(sv, strict, sb)] += 1
        if compare_reference_enabled:
            reference_pairs[(sv, ref_verdict, sb)] += 1
        if args.legacy_hints and sv == "unknown":
            hint = legacy_hint_signature(code)
            legacy_hints[(sb, strict, hint)] += 1
            for feature in projected_legacy_hint_features(hint):
                legacy_hint_features[(sb, strict, feature)] += 1
        if compare_legacy_enabled and lv == "possible" and strict == "impossible":
            virtual_legacy_possible += 1
        if sv != "unknown":
            non_unknown += 1
            if not compare_enabled:
                continue
            compare_non_unknown += 1
            if compare_legacy_enabled:
                strict_known = strict != "unknown"
                if strict_known:
                    legacy_compare_known += 1
                    if sv == lv:
                        legacy_known_match += 1
                    if sv == strict:
                        strict_known_match += 1
                if sv == lv:
                    legacy_match += 1
                elif lv == "unknown" and len(legacy_unknown_samples) < args.max_mismatches:
                    legacy_unknown_samples.append(f"{code}\tsymbolic={sv}/{sb}\tlegacy={lv}/{lc}\treason={lr}")
                elif lv != "unknown" and len(samples) < args.max_mismatches:
                    samples.append(f"{code}\tsymbolic={sv}/{sb}\tlegacy={lv}/{lc}\treason={lr}")
                if sv == strict:
                    strict_match += 1
                elif not (args.ignore_legacy_unknown and strict == "unknown") and len(strict_samples) < args.max_mismatches:
                    strict_samples.append(f"{code}\tsymbolic={sv}/{sb}\tstrict={strict}\tlegacy={lv}/{lc}\treason={lr}")
            if compare_reference_enabled:
                reference_known = ref_verdict != "unknown"
                if reference_known:
                    reference_compare_known += 1
                    if sv == ref_verdict:
                        reference_known_match += 1
                if sv == ref_verdict:
                    reference_match += 1
                elif ref_verdict != "unknown":
                    mismatch_tag = reference_mismatch_tag(sv, sb, ref_verdict)
                    reference_mismatch_tags[mismatch_tag] += 1
                    if len(reference_samples) < args.max_mismatches:
                        reference_samples.append(
                            f"{code}\tsymbolic={sv}/{sb}\treference={ref_verdict}/{ref_bucket}\ttag={mismatch_tag}"
                        )

    print(f"eval_total={total}")
    print(f"eval_skipped_by_layer={skipped_by_layer}")
    print(f"eval_skipped_by_bucket={skipped_by_bucket}")
    print(f"eval_non_unknown={non_unknown}")
    print(f"fallback_used={fallback_used}")
    print(f"kernel_used={kernel_used}")
    print(f"legacy_fallback_used={legacy_fallback_used}")
    print(f"decomposition_tree_checked={decomposition_tree_checked}")
    print(f"decomposition_tree_missing={decomposition_tree_missing}")
    print(f"decomposition_tree_open_tree_count={decomposition_tree_open_tree_count}")
    print(f"decomposition_tree_open_leaf_total={decomposition_tree_open_leaf_total}")
    if decomposition_tree_roots:
        print("decomposition_tree_roots:")
        for root_key, count in decomposition_tree_roots.most_common(20):
            print(f"  {root_key}: {count}")
    if decomposition_tree_dependencies:
        print("decomposition_tree_dependency_tags:")
        for dependency_tags, count in decomposition_tree_dependencies.most_common(20):
            label = ",".join(dependency_tags) if dependency_tags else "none"
            print(f"  {label}: {count}")
    if decomposition_tree_open_leaf_kinds:
        print("decomposition_tree_open_leaf_kinds:")
        for leaf_key, count in decomposition_tree_open_leaf_kinds.most_common(20):
            print(f"  {leaf_key}: {count}")
    compare_mode_for_report = "none" if args.no_compare_legacy else args.compare_against
    print(f"compare_against={compare_mode_for_report}")
    if compare_mode_for_report == "none":
        print("compare_total=0")
        print("compare_non_unknown=0")
        print("compare_known=0")
        print("legacy_match=NA")
        print("legacy_precision=NA")
        print("legacy_known_match=NA")
        print("legacy_known_precision=NA")
        print("strict_match=NA")
        print("strict_precision=NA")
        print("strict_known_match=NA")
        print("strict_known_precision=NA")
        print("virtual_legacy_possible=NA")
        print("reference_match=NA")
        print("reference_precision=NA")
        print("reference_known_match=NA")
        print("reference_known_precision=NA")
    elif compare_mode_for_report == "legacy":
        print(f"compare_total={compare_total}")
        print(f"compare_non_unknown={compare_non_unknown}")
        print(f"compare_known={legacy_compare_known}")
        print(f"legacy_match={legacy_match}")
        print(f"legacy_precision={100.0 * legacy_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"legacy_known_match={legacy_known_match}")
        print(f"legacy_known_precision={100.0 * legacy_known_match / legacy_compare_known if legacy_compare_known else 100:.6f}%")
        print(f"strict_match={strict_match}")
        print(f"strict_precision={100.0 * strict_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"strict_known_match={strict_known_match}")
        print(f"strict_known_precision={100.0 * strict_known_match / legacy_compare_known if legacy_compare_known else 100:.6f}%")
        print(f"virtual_legacy_possible={virtual_legacy_possible}")
        print("reference_match=NA")
        print("reference_precision=NA")
        print("reference_known_match=NA")
        print("reference_known_precision=NA")
    elif compare_mode_for_report == "reference":
        print(f"compare_total={compare_total}")
        print(f"compare_non_unknown={compare_non_unknown}")
        print(f"compare_known={reference_compare_known}")
        print("legacy_match=NA")
        print("legacy_precision=NA")
        print("legacy_known_match=NA")
        print("legacy_known_precision=NA")
        print("strict_match=NA")
        print("strict_precision=NA")
        print("strict_known_match=NA")
        print("strict_known_precision=NA")
        print("virtual_legacy_possible=NA")
        print(f"reference_match={reference_match}")
        print(f"reference_precision={100.0 * reference_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"reference_known_match={reference_known_match}")
        print(f"reference_known_precision={100.0 * reference_known_match / reference_compare_known if reference_compare_known else 100:.6f}%")
    else:
        print(f"compare_total={compare_total}")
        print(f"compare_non_unknown={compare_non_unknown}")
        print(f"legacy_compare_known={legacy_compare_known}")
        print(f"reference_compare_known={reference_compare_known}")
        print(f"legacy_match={legacy_match}")
        print(f"legacy_precision={100.0 * legacy_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"legacy_known_match={legacy_known_match}")
        print(f"legacy_known_precision={100.0 * legacy_known_match / legacy_compare_known if legacy_compare_known else 100:.6f}%")
        print(f"strict_match={strict_match}")
        print(f"strict_precision={100.0 * strict_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"strict_known_match={strict_known_match}")
        print(f"strict_known_precision={100.0 * strict_known_match / legacy_compare_known if legacy_compare_known else 100:.6f}%")
        print(f"virtual_legacy_possible={virtual_legacy_possible}")
        print(f"reference_match={reference_match}")
        print(f"reference_precision={100.0 * reference_match / compare_non_unknown if compare_non_unknown else 100:.6f}%")
        print(f"reference_known_match={reference_known_match}")
        print(f"reference_known_precision={100.0 * reference_known_match / reference_compare_known if reference_compare_known else 100:.6f}%")
    print(f"elapsed={time.perf_counter() - started:.6f}s")
    print(f"symbolic_time={symbolic_time:.6f}s")
    print(f"kernel_time={kernel_time:.6f}s")
    air_time = symbolic_time + kernel_time
    print(f"air_time={air_time:.6f}s")
    print(f"legacy_time={legacy_time:.6f}s")
    if selected_compare_mode in ("reference", "both"):
        print(f"reference_time={reference_time:.6f}s")
    else:
        print("reference_time=NA")
    if layer_counts:
        print("eval_layer_counts:")
        for layer_count, count in sorted(layer_counts.items()):
            print(f"  {layer_count}: {count}")
    if kernel_step_times:
        print("kernel_step_times:")
        for step, step_time in kernel_step_times.most_common():
            print(f"  {step}: {step_time:.6f}s")
        print("kernel_step_counts:")
        for step, count in kernel_step_counts.most_common():
            avg = kernel_step_times[step] / count if count else 0.0
            print(f"  {step}: {count} avg={avg:.9f}s")
    if HYBRID_RESCUE_STATS:
        print("hybrid_rescue_stats:")
        for key, count in sorted(HYBRID_RESCUE_STATS.items()):
            print(f"  {key}: {count}")
        print("hybrid_rescue_times:")
        for key, step_time in HYBRID_RESCUE_TIMES.most_common():
            calls = HYBRID_RESCUE_STATS.get(f"{key}_calls", 0)
            avg = step_time / calls if calls else 0.0
            print(f"  {key}: {step_time:.6f}s avg={avg:.9f}s")
    if CLAW_VERIFY_STATS:
        print("claw_verify_stats:")
        for key, count in sorted(CLAW_VERIFY_STATS.items()):
            print(f"  {key}: {count}")
        print("claw_verify_times:")
        calls = CLAW_VERIFY_STATS.get("calls", 0)
        for key, step_time in CLAW_VERIFY_TIMES.most_common():
            avg = step_time / calls if calls else 0.0
            print(f"  {key}: {step_time:.6f}s avg={avg:.9f}s")
    if PP_INVERSE_STATS:
        print("pp_inverse_stats:")
        for key, count in sorted(PP_INVERSE_STATS.items()):
            print(f"  {key}: {count}")
    if symbolic_time > 0 and legacy_time > 0:
        print(f"legacy_vs_symbolic={legacy_time / symbolic_time:.3f}x")
    else:
        print("legacy_vs_symbolic=NA")
    if air_time > 0 and legacy_time > 0:
        print(f"legacy_vs_air={legacy_time / air_time:.3f}x")
        print(f"air_speedup_over_legacy={legacy_time / air_time:.3f}x")
    else:
        print("legacy_vs_air=NA")
        print("air_speedup_over_legacy=NA")
    if symbolic_time > 0 and reference_time > 0:
        print(f"reference_vs_symbolic={reference_time / symbolic_time:.3f}x")
    else:
        print("reference_vs_symbolic=NA")
    if air_time > 0 and reference_time > 0:
        print(f"reference_vs_air={reference_time / air_time:.3f}x")
        print(f"reference_speedup_over_air={air_time / reference_time:.3f}x")
    else:
        print("reference_vs_air=NA")
        print("reference_speedup_over_air=NA")
    print("symbolic_buckets:")
    for (verdict, bucket), count in buckets.most_common(12):
        print(f"  {verdict}/{bucket}: {count}")
    if args.bucket_samples:
        print("bucket_samples:")
        for (verdict, bucket), count in buckets.most_common(12):
            samples_for_bucket = bucket_samples.get((verdict, bucket), [])
            if samples_for_bucket:
                print(f"  {verdict}/{bucket}:")
                for sample in samples_for_bucket:
                    print(f"    {sample}")
    if compare_mode_for_report in ("legacy", "both"):
        print("top_legacy_pairs:")
        for (sv, lv, bucket), count in legacy_pairs.most_common(12):
            print(f"  symbolic={sv}/{bucket} legacy={lv}: {count}")
        print("top_strict_pairs:")
        for (sv, strict, bucket), count in strict_pairs.most_common(12):
            print(f"  symbolic={sv}/{bucket} strict={strict}: {count}")
    if compare_mode_for_report in ("reference", "both"):
        print("top_reference_pairs:")
        for (sv, ref, bucket), count in reference_pairs.most_common(12):
            print(f"  symbolic={sv}/{bucket} reference={ref}: {count}")
        if reference_mismatch_tags:
            print("reference_mismatch_tags:")
            for tag, count in reference_mismatch_tags.most_common():
                print(f"  {tag}: {count}")
    if args.legacy_hints:
        print("top_legacy_hints_for_unknown:")
        for (bucket, strict, hint), count in legacy_hints.most_common(24):
            print(f"  {bucket} strict={strict} count={count} hint={hint}")
        print("top_projected_legacy_hint_features_for_unknown:")
        for (bucket, strict, feature), count in legacy_hint_features.most_common(40):
            print(f"  {bucket} strict={strict} count={count} feature={feature}")
    if samples:
        print("sample_legacy_known_mismatches:")
        for sample in samples:
            print(sample)
    if legacy_unknown_samples:
        print("sample_legacy_unknown_comparisons:")
        for sample in legacy_unknown_samples:
            print(sample)
    if strict_samples:
        print("sample_strict_mismatches:")
        for sample in strict_samples:
            print(sample)
    if reference_samples:
        print("sample_reference_mismatches:")
        for sample in reference_samples:
            print(sample)
    if decomposition_tree_samples:
        print("sample_missing_decomposition_trees:")
        for sample in decomposition_tree_samples:
            print(sample)
    if args.fail_on_unknown and non_unknown != total:
        return 1
    if args.fail_on_legacy_fallback and legacy_fallback_used:
        return 1
    if (
        args.fail_on_known_mismatch
        and (legacy_compare_known or reference_compare_known)
        and (
            (compare_mode_for_report in ("legacy", "both") and strict_known_match != legacy_compare_known)
            or (compare_mode_for_report in ("reference", "both") and reference_known_match != reference_compare_known)
        )
    ):
        return 1
    if args.fail_on_missing_decomposition_tree and decomposition_tree_missing:
        return 1
    if args.fail_on_open_decomposition_leaf and decomposition_tree_open_leaf_total:
        return 1
    return 1 if strict_samples else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a prefix-free symbolic frontier automaton.")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--max-states", type=int, default=200_000)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--progress-every", type=int, default=1000)
    parser.add_argument("--mermaid", action="store_true")
    parser.add_argument("--bucket-graph", action="store_true")
    parser.add_argument("--automaton-graph", action="store_true")
    parser.add_argument("--automaton-graph-limit", type=int, default=120)
    parser.add_argument("--decision-graph", action="store_true")
    parser.add_argument("--corner-mode", choices=("none", "raw", "quotient"), default="none")
    parser.add_argument("--corner-dfa", action="store_true")
    parser.add_argument("--frontier-cutoff", action="store_true")
    parser.add_argument("--rotate-canonical", action="store_true")
    parser.add_argument(
        "--experiment",
        action="append",
        choices=(
            "promote-opposite",
            "promote-claw-bottom",
            "promote-top-single-c",
            "promote-full-pin",
            "promote-no-c",
            "split-opposite",
            "promote-closed-c",
            "promote-empty-opposite",
            "promote-dead-opposite-tail",
            "promote-top-three-s",
            "split-cut",
            "promote-scaffold-pppp-no-opp-s",
            "stackability-core",
            "stackability-swap12-core",
            "reference-stackability-core",
            "reference-cpcp",
            "reference-derived-positive",
            "claw-tail-seed-core",
            "pp-inverse-predecessor-core",
            "zero-stack-pp-predecessor-core",
            "defer-swap-positive",
        ),
        default=[],
    )
    parser.add_argument("--eval-data", type=Path)
    parser.add_argument("--eval-limit", type=int, default=5000)
    parser.add_argument("--eval-max-seconds", type=float, default=0.0)
    parser.add_argument("--eval-min-layers", type=int, default=0)
    parser.add_argument("--eval-max-layers", type=int, default=0)
    parser.add_argument("--eval-skip-bucket-regex", type=str, default="")
    parser.add_argument("--eval-per-file", type=int, default=0)
    parser.add_argument("--no-eval-shuffle", action="store_true")
    parser.add_argument("--eval-random", type=int, default=0, metavar="N")
    parser.add_argument("--eval-random-layers", type=int, default=5)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--max-mismatches", type=int, default=10)
    parser.add_argument("--legacy-hints", action="store_true")
    parser.add_argument("--bucket-samples", type=int, default=0)
    parser.add_argument("--compare-limit", type=int, default=0)
    parser.add_argument("--compare-every", type=int, default=1)
    parser.add_argument("--compare-against", choices=("legacy", "reference", "both", "none"), default="legacy")
    parser.add_argument("--ignore-legacy-unknown", action="store_true")
    parser.add_argument("--fail-on-unknown", action="store_true")
    parser.add_argument("--fail-on-legacy-fallback", action="store_true")
    parser.add_argument("--fail-on-known-mismatch", action="store_true")
    parser.add_argument("--fail-on-missing-decomposition-tree", action="store_true")
    parser.add_argument("--fail-on-open-decomposition-leaf", action="store_true")
    parser.add_argument(
        "--fallback",
        choices=("none", "physics-core", "swap-core", "legacy-core", "kernel-core", "kernel-hybrid-core"),
        default="none",
    )
    parser.add_argument("--no-compare-legacy", action="store_true")
    args = parser.parse_args()

    corner_mode = "raw" if args.corner_dfa else args.corner_mode
    if args.eval_data or args.eval_random:
        return run_eval(args, corner_mode)

    automaton = SymbolicFrontierAutomaton(
        corner_mode=corner_mode,
        max_depth=args.depth,
        rotate_canonical=args.rotate_canonical,
        experiments=frozenset(args.experiment),
    )
    states, edge_count, dead_edges, truncated, bucket_edges = automaton.build_reachable(
        args.depth,
        args.max_states,
        args.max_seconds,
        args.progress_every,
        args.bucket_graph,
        args.frontier_cutoff,
    )
    buckets = Counter(
        automaton.terminal_bucket(s)
        for s in states
        if s.depth == args.depth or automaton.is_absorbing_bucket(automaton.terminal_bucket(s), args.frontier_cutoff)
    )
    print(f"depth={args.depth}")
    print(f"states={len(states)}")
    print(f"edges={edge_count}")
    print(f"dead_edges={dead_edges}")
    print(f"truncated={truncated}")
    print(f"corner_mode={corner_mode}")
    print(f"rotate_canonical={args.rotate_canonical}")
    print("experiments=" + (",".join(args.experiment) if args.experiment else "none"))
    if automaton.corner_quotient is not None:
        print("corner_quotient_classes=" + ",".join(str(count) for count in automaton.corner_quotient.class_counts()))
    print("terminal_buckets:")
    for bucket, count in buckets.most_common():
        print(f"  {bucket}: {count}")
    if args.mermaid:
        print()
        print(mermaid_summary(buckets))
    if args.decision_graph:
        print()
        print(mermaid_decision_graph())
    if args.bucket_graph:
        print()
        print(mermaid_bucket_graph(bucket_edges))
    if args.automaton_graph:
        print()
        print(mermaid_automaton_graph(automaton, states, args.automaton_graph_limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
