from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Sequence

from .protocols import LayerFamilyAutomaton

RowSignature = tuple[int, int, int, int]


@dataclass(frozen=True)
class UnionLayerAutomaton:
    """Deterministic finite union of layer-family automata."""

    families: tuple[LayerFamilyAutomaton, ...]
    name: str = "union"

    def __init__(self, families: Sequence[LayerFamilyAutomaton], name: str = "union"):
        object.__setattr__(self, "families", tuple(families))
        object.__setattr__(self, "name", name)
        if not self.families:
            raise ValueError("union requires at least one family")

    def start_state(self):
        return tuple(family.start_state() for family in self.families)

    def advance(self, state, row_signature: RowSignature):
        next_states = []
        live = False
        for family, member_state in zip(self.families, state):
            if member_state is None:
                next_states.append(None)
                continue
            nxt = family.advance(member_state, row_signature)
            next_states.append(nxt)
            live = live or nxt is not None
        return tuple(next_states) if live else None

    def accepts(self, state) -> bool:
        return any(
            member_state is not None and family.accepts(member_state)
            for family, member_state in zip(self.families, state)
        )


@dataclass(frozen=True)
class IntersectionLayerAutomaton:
    """Deterministic finite intersection of layer-family automata."""

    families: tuple[LayerFamilyAutomaton, ...]
    name: str = "intersection"

    def __init__(
        self,
        families: Sequence[LayerFamilyAutomaton],
        name: str = "intersection",
    ):
        object.__setattr__(self, "families", tuple(families))
        object.__setattr__(self, "name", name)
        if not self.families:
            raise ValueError("intersection requires at least one family")

    def start_state(self):
        return tuple(family.start_state() for family in self.families)

    def advance(self, state, row_signature: RowSignature):
        next_states = []
        for family, member_state in zip(self.families, state):
            nxt = family.advance(member_state, row_signature)
            if nxt is None:
                return None
            next_states.append(nxt)
        return tuple(next_states)

    def accepts(self, state) -> bool:
        return all(
            family.accepts(member_state)
            for family, member_state in zip(self.families, state)
        )


@dataclass(frozen=True)
class DifferenceLayerAutomaton:
    r"""Language difference ``left \ right`` for deterministic automata.

    A dead right-hand state remains dead/rejecting while the left side keeps
    scanning.  A dead left-hand state kills the product immediately.
    """

    left: LayerFamilyAutomaton
    right: LayerFamilyAutomaton
    name: str = "difference"

    def start_state(self):
        return (self.left.start_state(), self.right.start_state())

    def advance(self, state, row_signature: RowSignature):
        left_state, right_state = state
        next_left = self.left.advance(left_state, row_signature)
        if next_left is None:
            return None
        next_right = (
            None
            if right_state is None
            else self.right.advance(right_state, row_signature)
        )
        return (next_left, next_right)

    def accepts(self, state) -> bool:
        left_state, right_state = state
        return self.left.accepts(left_state) and not (
            right_state is not None and self.right.accepts(right_state)
        )


def accepts_rows(automaton: LayerFamilyAutomaton, rows: Sequence[RowSignature]) -> bool:
    """Small representation-independent membership helper for tests/tools."""

    state = automaton.start_state()
    for row in rows:
        state = automaton.advance(state, row)
        if state is None:
            return False
    return automaton.accepts(state)
