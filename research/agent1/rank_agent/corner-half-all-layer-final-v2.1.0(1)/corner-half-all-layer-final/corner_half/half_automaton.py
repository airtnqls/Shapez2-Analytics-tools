"""Exact minimized all-layer DFA for buildable quad east halves.

A normalized east half is a word over the 16-symbol row alphabet
``{--,-S,-P,-c,S-,...,cc}``, read bottom to top, with trailing ``--`` rows
removed.  The language is exactly

    Corner(left) ∧ Corner(right) ∧ Stable(left,right).

The first two conjuncts use the 19-state minimal Corner DFA.  Joint stability
has a six-state minimal DFA.  Their reachable product has 552 states and
Hopcroft minimization yields 210 states.  The 210-state machine is minimal for
oriented normalized half words.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

from .corner_dfa import ALPHABET as CELL_ALPHABET, build_minimized_dfa

ROW_ALPHABET: tuple[str, ...] = tuple(
    a + b for a in CELL_ALPHABET for b in CELL_ALPHABET
)
ROW_INDEX = {row: i for i, row in enumerate(ROW_ALPHABET)}

# Six-state exact stability automaton for a normalized two-column strip.
#
# 0 G  : stable prefix; top boundary has both columns occupied, or prefix empty
# 1 D  : permanently dead / normalized trailing-empty sink
# 2 R  : stable prefix; only right top column is occupied
# 3 L  : stable prefix; only left top column is occupied
# 4 UL : unresolved left crystal chain, supported right pin frontier
# 5 UR : unresolved right crystal chain, supported left pin frontier
#
# Accepting states are G, R, L.  UL/UR can still be rescued by future rows.
STABILITY_STATE_NAMES = ("G", "D", "R", "L", "UL", "UR")
STABILITY_START = 0
STABILITY_ACCEPTING = frozenset({0, 2, 3})


def _stability_row_map(groups: dict[int, Iterable[str]]) -> tuple[int, ...]:
    out = [-1] * len(ROW_ALPHABET)
    for target, rows in groups.items():
        for row in rows:
            out[ROW_INDEX[row]] = target
    if any(x < 0 for x in out):
        missing = [ROW_ALPHABET[i] for i, x in enumerate(out) if x < 0]
        raise AssertionError(f"incomplete stability transition row: {missing}")
    return tuple(out)


STABILITY_TRANSITIONS: tuple[tuple[int, ...], ...] = (
    _stability_row_map(
        {
            0: ("SS", "SP", "Sc", "PS", "PP", "Pc", "cS", "cP", "cc"),
            1: ("--",),
            2: ("-S", "-P", "-c"),
            3: ("S-", "P-", "c-"),
        }
    ),
    tuple(1 for _ in ROW_ALPHABET),
    _stability_row_map(
        {
            0: ("SS", "Sc", "cS", "cc"),
            1: ("--", "S-", "SP", "P-", "PS", "PP", "Pc", "c-"),
            2: ("-S", "-P", "-c"),
            4: ("cP",),
        }
    ),
    _stability_row_map(
        {
            0: ("SS", "Sc", "cS", "cc"),
            1: ("--", "-S", "-P", "-c", "SP", "PS", "PP", "cP"),
            3: ("S-", "P-", "c-"),
            5: ("Pc",),
        }
    ),
    _stability_row_map(
        {
            0: ("cS", "cc"),
            1: (
                "--", "-S", "-P", "-c", "S-", "SS", "SP", "Sc",
                "P-", "PS", "PP", "Pc", "c-",
            ),
            4: ("cP",),
        }
    ),
    _stability_row_map(
        {
            0: ("Sc", "cc"),
            1: (
                "--", "-S", "-P", "-c", "S-", "SS", "SP",
                "P-", "PS", "PP", "c-", "cS", "cP",
            ),
            5: ("Pc",),
        }
    ),
)


@dataclass(frozen=True)
class HalfDFA:
    transitions: tuple[tuple[int, ...], ...]
    start: int
    accepting: frozenset[int]
    representatives: tuple[str, ...]
    raw_reachable_states: int
    raw_product_bound: int

    @property
    def state_count(self) -> int:
        return len(self.transitions)

    def step(self, state: int, row: str) -> int:
        try:
            symbol = ROW_INDEX[row]
        except KeyError as exc:
            raise ValueError(f"invalid half row {row!r}") from exc
        return self.transitions[state][symbol]

    def accepts_rows(self, rows: Sequence[str]) -> bool:
        state = self.start
        for row in normalize_half_rows(rows):
            state = self.step(state, row)
        return state in self.accepting

    def accepts(self, code_or_rows: str | Sequence[str]) -> bool:
        rows = parse_half_rows(code_or_rows) if isinstance(code_or_rows, str) else code_or_rows
        return self.accepts_rows(rows)

    def count_exact_height(self, height: int) -> int:
        """Count normalized accepted halves of exactly ``height`` rows."""
        if height < 0:
            raise ValueError("height must be nonnegative")
        if height == 0:
            return int(self.start in self.accepting)
        dp = [0] * self.state_count
        dp[self.start] = 1
        for layer in range(height):
            nxt = [0] * self.state_count
            symbols = range(len(ROW_ALPHABET))
            if layer == height - 1:
                symbols = [i for i, row in enumerate(ROW_ALPHABET) if row != "--"]
            for state, count in enumerate(dp):
                if not count:
                    continue
                for symbol in symbols:
                    nxt[self.transitions[state][symbol]] += count
            dp = nxt
        return sum(dp[state] for state in self.accepting)

    def counts_by_height(self, cap: int) -> tuple[int, ...]:
        """Return exact normalized counts for heights 0..cap in Θ(cap)."""
        if cap < 0:
            raise ValueError("cap must be nonnegative")
        counts = [int(self.start in self.accepting)]
        dp = [0] * self.state_count
        dp[self.start] = 1
        nonempty_symbols = [
            i for i, row in enumerate(ROW_ALPHABET) if row != "--"
        ]
        for _height in range(1, cap + 1):
            exact = 0
            for state, count in enumerate(dp):
                if not count:
                    continue
                for symbol in nonempty_symbols:
                    if self.transitions[state][symbol] in self.accepting:
                        exact += count
            counts.append(exact)

            nxt = [0] * self.state_count
            for state, count in enumerate(dp):
                if not count:
                    continue
                for symbol in range(len(ROW_ALPHABET)):
                    nxt[self.transitions[state][symbol]] += count
            dp = nxt
        return tuple(counts)

    def count_up_to_cap(self, cap: int) -> int:
        return sum(self.counts_by_height(cap))




@dataclass(frozen=True)
class StabilityMinimalityAudit:
    states: int
    reachable: int
    distinguishable_pairs: int
    total_pairs: int
    max_distinguishing_suffix: int
    minimal: bool


@dataclass(frozen=True)
class MinimalityAudit:
    states: int
    reachable: int
    distinguishable_pairs: int
    total_pairs: int
    max_distinguishing_suffix: int
    max_representative_height: int
    minimal: bool


def parse_half_rows(code: str) -> tuple[str, ...]:
    if not code:
        return ()
    rows: list[str] = []
    for raw in code.split(":"):
        if len(raw) == 4:
            if raw[2:] != "--":
                raise ValueError("half code must occupy only columns 0 and 1")
            raw = raw[:2]
        if len(raw) != 2 or any(ch not in CELL_ALPHABET for ch in raw):
            raise ValueError(f"invalid half row {raw!r}")
        rows.append(raw)
    return normalize_half_rows(rows)


def normalize_half_rows(rows: Sequence[str]) -> tuple[str, ...]:
    normalized = list(rows)
    for row in normalized:
        if row not in ROW_INDEX:
            raise ValueError(f"invalid half row {row!r}")
    while normalized and normalized[-1] == "--":
        normalized.pop()
    return tuple(normalized)


def stability_accepts_rows(rows: Sequence[str]) -> bool:
    state = STABILITY_START
    for row in normalize_half_rows(rows):
        state = STABILITY_TRANSITIONS[state][ROW_INDEX[row]]
    return state in STABILITY_ACCEPTING


def _reachable_product() -> tuple[
    list[tuple[int, int, int]],
    list[tuple[int, ...]],
    list[bool],
    list[str],
]:
    corner = build_minimized_dfa()
    start = (corner.start, corner.start, STABILITY_START)
    states = [start]
    index = {start: 0}
    representatives = [""]
    transitions: list[tuple[int, ...]] = []
    accepting: list[bool] = []
    head = 0
    while head < len(states):
        left, right, stable = states[head]
        row_transitions: list[int] = []
        for symbol, row in enumerate(ROW_ALPHABET):
            nxt = (
                corner.step(left, row[0]),
                corner.step(right, row[1]),
                STABILITY_TRANSITIONS[stable][symbol],
            )
            if nxt not in index:
                index[nxt] = len(states)
                states.append(nxt)
                prefix = representatives[head]
                representatives.append(prefix + ((":" if prefix else "") + row))
            row_transitions.append(index[nxt])
        transitions.append(tuple(row_transitions))
        accepting.append(
            left != corner.reject
            and right != corner.reject
            and stable in STABILITY_ACCEPTING
        )
        head += 1
    return states, transitions, accepting, representatives


def _hopcroft(
    transitions: Sequence[Sequence[int]], accepting: Sequence[bool]
) -> list[set[int]]:
    n = len(transitions)
    alphabet = len(ROW_ALPHABET)
    yes = {i for i, value in enumerate(accepting) if value}
    no = set(range(n)) - yes
    partition = [block for block in (yes, no) if block]
    work = [min(partition, key=len).copy()]

    inverse: list[list[list[int]]] = [
        [[] for _ in range(n)] for _ in range(alphabet)
    ]
    for src, row in enumerate(transitions):
        for symbol, dst in enumerate(row):
            inverse[symbol][dst].append(src)

    while work:
        splitter = work.pop()
        for symbol in range(alphabet):
            preimage: set[int] = set()
            for dst in splitter:
                preimage.update(inverse[symbol][dst])
            if not preimage:
                continue
            refined: list[set[int]] = []
            for block in partition:
                inside = block & preimage
                outside = block - preimage
                if inside and outside:
                    refined.extend((inside, outside))
                    found = next((i for i, old in enumerate(work) if old == block), None)
                    if found is not None:
                        work.pop(found)
                        work.extend((inside, outside))
                    else:
                        work.append(inside if len(inside) <= len(outside) else outside)
                else:
                    refined.append(block)
            partition = refined
    return partition


def _canonicalize_minimized(
    raw_transitions: Sequence[Sequence[int]],
    raw_accepting: Sequence[bool],
    raw_representatives: Sequence[str],
    partition: Sequence[set[int]],
) -> HalfDFA:
    raw_to_block = {
        raw: block_id for block_id, block in enumerate(partition) for raw in block
    }
    block_transitions: list[tuple[int, ...]] = []
    block_accepting: list[bool] = []
    block_representatives: list[str] = []
    for block in partition:
        representative = min(block, key=lambda raw: (raw_representatives[raw].count(":"), len(raw_representatives[raw]), raw_representatives[raw]))
        block_transitions.append(
            tuple(raw_to_block[dst] for dst in raw_transitions[representative])
        )
        block_accepting.append(raw_accepting[representative])
        block_representatives.append(raw_representatives[representative])

    old_start = raw_to_block[0]
    order: list[int] = []
    seen = {old_start}
    todo = deque([old_start])
    while todo:
        state = todo.popleft()
        order.append(state)
        for nxt in block_transitions[state]:
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    if len(order) != len(partition):
        raise AssertionError("minimized DFA contains unreachable blocks")
    new_id = {old: new for new, old in enumerate(order)}
    transitions = tuple(
        tuple(new_id[nxt] for nxt in block_transitions[old]) for old in order
    )
    accepting = frozenset(
        new_id[old] for old in order if block_accepting[old]
    )
    representatives = tuple(block_representatives[old] for old in order)
    return HalfDFA(
        transitions=transitions,
        start=0,
        accepting=accepting,
        representatives=representatives,
        raw_reachable_states=len(raw_transitions),
        raw_product_bound=19 * 19 * 6,
    )


@lru_cache(maxsize=1)
def rebuild_minimized_half_dfa() -> HalfDFA:
    _states, transitions, accepting, representatives = _reachable_product()
    partition = _hopcroft(transitions, accepting)
    dfa = _canonicalize_minimized(
        transitions, accepting, representatives, partition
    )
    if dfa.state_count != 210:
        raise AssertionError(f"unexpected Half DFA size {dfa.state_count}, expected 210")
    return dfa



def audit_stability_minimality() -> StabilityMinimalityAudit:
    n = len(STABILITY_TRANSITIONS)
    reachable = {STABILITY_START}
    todo = deque([STABILITY_START])
    while todo:
        state = todo.popleft()
        for nxt in STABILITY_TRANSITIONS[state]:
            if nxt not in reachable:
                reachable.add(nxt)
                todo.append(nxt)

    pairs: list[tuple[int, int]] = []
    pair_index: dict[tuple[int, int], int] = {}
    for a in range(n):
        for b in range(a + 1, n):
            pair_index[(a, b)] = len(pairs)
            pairs.append((a, b))
    reverse: list[list[int]] = [[] for _ in pairs]
    distance = [-1] * len(pairs)
    queue: deque[int] = deque()
    for pid, (a, b) in enumerate(pairs):
        if (a in STABILITY_ACCEPTING) != (b in STABILITY_ACCEPTING):
            distance[pid] = 0
            queue.append(pid)
    for pid, (a, b) in enumerate(pairs):
        for symbol in range(len(ROW_ALPHABET)):
            x = STABILITY_TRANSITIONS[a][symbol]
            y = STABILITY_TRANSITIONS[b][symbol]
            if x == y:
                continue
            key = (x, y) if x < y else (y, x)
            reverse[pair_index[key]].append(pid)
    while queue:
        target = queue.popleft()
        for source in reverse[target]:
            if distance[source] < 0:
                distance[source] = distance[target] + 1
                queue.append(source)
    distinguished = sum(value >= 0 for value in distance)
    total = len(pairs)
    return StabilityMinimalityAudit(
        states=n,
        reachable=len(reachable),
        distinguishable_pairs=distinguished,
        total_pairs=total,
        max_distinguishing_suffix=max(distance, default=0),
        minimal=(len(reachable) == n and distinguished == total),
    )


def audit_minimality(dfa: HalfDFA | None = None) -> MinimalityAudit:
    """Constructively verify reachability and pairwise distinguishability."""
    if dfa is None:
        dfa = build_minimized_half_dfa()
    n = dfa.state_count

    # Reachability from start.
    reachable = {dfa.start}
    todo = deque([dfa.start])
    while todo:
        state = todo.popleft()
        for nxt in dfa.transitions[state]:
            if nxt not in reachable:
                reachable.add(nxt)
                todo.append(nxt)

    # Reverse BFS on unordered state pairs.  A pair is initially distinguished
    # when exactly one endpoint is accepting; predecessors inherit the same
    # distinguishing suffix with one row prepended.
    pair_index: dict[tuple[int, int], int] = {}
    pairs: list[tuple[int, int]] = []
    for a in range(n):
        for b in range(a + 1, n):
            pair_index[(a, b)] = len(pairs)
            pairs.append((a, b))
    reverse: list[list[int]] = [[] for _ in pairs]
    distinguished = [False] * len(pairs)
    distance = [-1] * len(pairs)
    queue: deque[int] = deque()
    for pid, (a, b) in enumerate(pairs):
        if (a in dfa.accepting) != (b in dfa.accepting):
            distinguished[pid] = True
            distance[pid] = 0
            queue.append(pid)
    for pid, (a, b) in enumerate(pairs):
        for symbol in range(len(ROW_ALPHABET)):
            x, y = dfa.transitions[a][symbol], dfa.transitions[b][symbol]
            if x == y:
                continue
            key = (x, y) if x < y else (y, x)
            reverse[pair_index[key]].append(pid)
    while queue:
        target = queue.popleft()
        for source in reverse[target]:
            if not distinguished[source]:
                distinguished[source] = True
                distance[source] = distance[target] + 1
                queue.append(source)
    count = sum(distinguished)
    total = len(pairs)
    representative_heights = [
        0 if not value else value.count(":") + 1
        for value in dfa.representatives
    ]
    return MinimalityAudit(
        states=n,
        reachable=len(reachable),
        distinguishable_pairs=count,
        total_pairs=total,
        max_distinguishing_suffix=max(distance, default=0),
        max_representative_height=max(representative_heights, default=0),
        minimal=(len(reachable) == n and count == total),
    )


from .half_dfa_table import (
    ACCEPTING as _FROZEN_ACCEPTING,
    RAW_PRODUCT_BOUND as _FROZEN_RAW_PRODUCT_BOUND,
    RAW_REACHABLE_STATES as _FROZEN_RAW_REACHABLE_STATES,
    REPRESENTATIVES as _FROZEN_REPRESENTATIVES,
    START as _FROZEN_START,
    TRANSITIONS as _FROZEN_TRANSITIONS,
)

HALF_DFA = HalfDFA(
    transitions=_FROZEN_TRANSITIONS,
    start=_FROZEN_START,
    accepting=_FROZEN_ACCEPTING,
    representatives=_FROZEN_REPRESENTATIVES,
    raw_reachable_states=_FROZEN_RAW_REACHABLE_STATES,
    raw_product_bound=_FROZEN_RAW_PRODUCT_BOUND,
)


def build_minimized_half_dfa() -> HalfDFA:
    """Return the frozen audited minimal DFA without rebuilding Hopcroft."""
    return HALF_DFA


def audit_frozen_table() -> bool:
    rebuilt = rebuild_minimized_half_dfa()
    return rebuilt == HALF_DFA


__all__ = [
    "HALF_DFA",
    "HalfDFA",
    "MinimalityAudit",
    "StabilityMinimalityAudit",
    "ROW_ALPHABET",
    "ROW_INDEX",
    "STABILITY_ACCEPTING",
    "STABILITY_START",
    "STABILITY_STATE_NAMES",
    "STABILITY_TRANSITIONS",
    "audit_frozen_table",
    "audit_minimality",
    "audit_stability_minimality",
    "build_minimized_half_dfa",
    "rebuild_minimized_half_dfa",
    "normalize_half_rows",
    "parse_half_rows",
    "stability_accepts_rows",
]
