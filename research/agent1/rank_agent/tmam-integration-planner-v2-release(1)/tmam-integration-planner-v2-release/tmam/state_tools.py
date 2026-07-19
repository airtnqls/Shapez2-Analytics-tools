from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Generic, Hashable, Iterable, Mapping, TypeVar

StateT = TypeVar("StateT", bound=Hashable)
SymbolT = TypeVar("SymbolT", bound=Hashable)


class StateInterner(Generic[StateT]):
    """Assign stable dense integer IDs to equal semantic states."""

    def __init__(self) -> None:
        self._state_to_id: dict[StateT, int] = {}
        self._states: list[StateT] = []

    def intern(self, state: StateT) -> int:
        existing = self._state_to_id.get(state)
        if existing is not None:
            return existing
        identifier = len(self._states)
        self._state_to_id[state] = identifier
        self._states.append(state)
        return identifier

    def state(self, identifier: int) -> StateT:
        return self._states[identifier]

    @property
    def states(self) -> tuple[StateT, ...]:
        return tuple(self._states)

    def __len__(self) -> int:
        return len(self._states)


@dataclass(frozen=True)
class AutomatonMetrics:
    states: int
    reachable_states: int
    accepting_states: int
    transitions: int
    alphabet_size: int
    unreachable_states: int


def generic_reachable_states(
    start: StateT,
    alphabet: Iterable[SymbolT],
    transition: Callable[[StateT, SymbolT], StateT],
) -> frozenset[StateT]:
    symbols = tuple(alphabet)
    seen = {start}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        for symbol in symbols:
            nxt = transition(state, symbol)
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return frozenset(seen)


def automaton_metrics(dfa) -> AutomatonMetrics:
    reachable = dfa.reachable_states()
    return AutomatonMetrics(
        states=len(dfa.states),
        reachable_states=len(reachable),
        accepting_states=len(dfa.accepting),
        transitions=len(dfa.transition),
        alphabet_size=len(dfa.alphabet),
        unreachable_states=len(dfa.states) - len(reachable),
    )
