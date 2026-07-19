from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Generic, Hashable, Iterable, Mapping, TypeVar

StateT = TypeVar("StateT", bound=Hashable)
SymbolT = TypeVar("SymbolT", bound=Hashable)


@dataclass(frozen=True)
class DFA(Generic[StateT, SymbolT]):
    alphabet: tuple[SymbolT, ...]
    states: frozenset[StateT]
    start: StateT
    accepting: frozenset[StateT]
    transition: Mapping[tuple[StateT, SymbolT], StateT]

    def __post_init__(self) -> None:
        if self.start not in self.states:
            raise ValueError("start state is missing")
        if not self.accepting <= self.states:
            raise ValueError("accepting states are not a subset of states")
        missing = [
            (state, symbol)
            for state in self.states
            for symbol in self.alphabet
            if (state, symbol) not in self.transition
        ]
        if missing:
            raise ValueError(f"DFA transition function is incomplete; first missing={missing[0]!r}")

    def step(self, state: StateT, symbol: SymbolT) -> StateT:
        return self.transition[(state, symbol)]

    def accepts(self, word: Iterable[SymbolT]) -> bool:
        state = self.start
        for symbol in word:
            state = self.step(state, symbol)
        return state in self.accepting

    def reachable_states(self) -> frozenset[StateT]:
        seen = {self.start}
        queue = deque([self.start])
        while queue:
            state = queue.popleft()
            for symbol in self.alphabet:
                nxt = self.step(state, symbol)
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return frozenset(seen)

    def trim(self) -> "DFA[StateT, SymbolT]":
        reachable = self.reachable_states()
        transition = {
            (state, symbol): self.step(state, symbol)
            for state in reachable
            for symbol in self.alphabet
        }
        return DFA(
            self.alphabet,
            reachable,
            self.start,
            self.accepting & reachable,
            transition,
        )


@dataclass(frozen=True)
class MinimizedDFA(Generic[SymbolT]):
    dfa: DFA[int, SymbolT]
    old_to_new: Mapping[Hashable, int]
    blocks: tuple[frozenset[Hashable], ...]


def minimize_dfa(dfa: DFA[StateT, SymbolT]) -> MinimizedDFA[SymbolT]:
    """Deterministic partition refinement with stable numbering."""

    dfa = dfa.trim()
    accepting = set(dfa.accepting)
    rejecting = set(dfa.states) - accepting
    blocks: list[set[StateT]] = [block for block in (accepting, rejecting) if block]

    changed = True
    while changed:
        changed = False
        block_index = {state: index for index, block in enumerate(blocks) for state in block}
        refined: list[set[StateT]] = []
        for block in blocks:
            buckets: dict[tuple[int, ...], set[StateT]] = {}
            for state in block:
                signature = tuple(block_index[dfa.step(state, symbol)] for symbol in dfa.alphabet)
                buckets.setdefault(signature, set()).add(state)
            refined.extend(buckets.values())
            if len(buckets) > 1:
                changed = True
        blocks = refined

    blocks.sort(key=lambda block: min(map(repr, block)))
    mapping = {state: index for index, block in enumerate(blocks) for state in block}
    transition: dict[tuple[int, SymbolT], int] = {}
    for index, block in enumerate(blocks):
        representative = next(iter(block))
        for symbol in dfa.alphabet:
            transition[(index, symbol)] = mapping[dfa.step(representative, symbol)]

    minimized = DFA(
        alphabet=dfa.alphabet,
        states=frozenset(range(len(blocks))),
        start=mapping[dfa.start],
        accepting=frozenset(mapping[state] for state in dfa.accepting),
        transition=transition,
    )
    return MinimizedDFA(minimized, mapping, tuple(frozenset(block) for block in blocks))


def distinguishing_word(
    left: DFA[StateT, SymbolT],
    right: DFA[StateT, SymbolT],
) -> tuple[SymbolT, ...] | None:
    """Shortest word on which two DFAs disagree, or None if equivalent."""

    if left.alphabet != right.alphabet:
        raise ValueError("alphabets differ")
    queue = deque([(left.start, right.start, ())])
    seen = {(left.start, right.start)}
    while queue:
        lstate, rstate, word = queue.popleft()
        if (lstate in left.accepting) != (rstate in right.accepting):
            return word
        for symbol in left.alphabet:
            pair = (left.step(lstate, symbol), right.step(rstate, symbol))
            if pair not in seen:
                seen.add(pair)
                queue.append((pair[0], pair[1], word + (symbol,)))
    return None


def product_dfa(
    left: DFA[StateT, SymbolT],
    right: DFA[Hashable, SymbolT],
    *,
    accept_when,
) -> DFA[tuple[StateT, Hashable], SymbolT]:
    if left.alphabet != right.alphabet:
        raise ValueError("alphabets differ")
    states = frozenset((l, r) for l in left.states for r in right.states)
    transition = {
        ((l, r), symbol): (left.step(l, symbol), right.step(r, symbol))
        for l, r in states
        for symbol in left.alphabet
    }
    accepting = frozenset(
        (l, r)
        for l, r in states
        if accept_when(l in left.accepting, r in right.accepting)
    )
    return DFA(left.alphabet, states, (left.start, right.start), accepting, transition)
