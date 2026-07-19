from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Hashable, Iterable, TypeVar

from .automata import DFA, MinimizedDFA, distinguishing_word, minimize_dfa, product_dfa

SymbolT = TypeVar("SymbolT", bound=Hashable)
StateT = TypeVar("StateT", bound=Hashable)


@dataclass(frozen=True)
class AutomatonFamily(Generic[SymbolT]):
    family_id: str
    automaton: DFA[Hashable, SymbolT]
    description: str = ""

    def contains(self, word: Iterable[SymbolT]) -> bool:
        return self.automaton.accepts(word)

    def minimized(self) -> "AutomatonFamily[SymbolT]":
        result = minimize_dfa(self.automaton)
        return AutomatonFamily(self.family_id, result.dfa, self.description)

    def union(self, other: "AutomatonFamily[SymbolT]", *, family_id: str) -> "AutomatonFamily[SymbolT]":
        return AutomatonFamily(
            family_id,
            product_dfa(self.automaton, other.automaton, accept_when=lambda a, b: a or b),
            f"{self.family_id} union {other.family_id}",
        ).minimized()

    def intersection(
        self,
        other: "AutomatonFamily[SymbolT]",
        *,
        family_id: str,
    ) -> "AutomatonFamily[SymbolT]":
        return AutomatonFamily(
            family_id,
            product_dfa(self.automaton, other.automaton, accept_when=lambda a, b: a and b),
            f"{self.family_id} intersection {other.family_id}",
        ).minimized()

    def difference(
        self,
        other: "AutomatonFamily[SymbolT]",
        *,
        family_id: str,
    ) -> "AutomatonFamily[SymbolT]":
        return AutomatonFamily(
            family_id,
            product_dfa(self.automaton, other.automaton, accept_when=lambda a, b: a and not b),
            f"{self.family_id} minus {other.family_id}",
        ).minimized()


@dataclass(frozen=True)
class FamilyStage(Generic[SymbolT]):
    rank: int
    family: AutomatonFamily[SymbolT]
    state_count: int
    stabilized_against_previous: bool
    counterexample: tuple[SymbolT, ...] | None


class RankedFamilySequence(Generic[SymbolT]):
    """Audit helper for symbolic PP-rank/family closure research."""

    def __init__(self) -> None:
        self._stages: list[FamilyStage[SymbolT]] = []

    @property
    def stages(self) -> tuple[FamilyStage[SymbolT], ...]:
        return tuple(self._stages)

    def append(self, rank: int, family: AutomatonFamily[SymbolT]) -> FamilyStage[SymbolT]:
        minimized = family.minimized()
        counterexample = None
        stabilized = False
        if self._stages:
            counterexample = distinguishing_word(
                self._stages[-1].family.automaton,
                minimized.automaton,
            )
            stabilized = counterexample is None
        stage = FamilyStage(
            rank=rank,
            family=minimized,
            state_count=len(minimized.automaton.states),
            stabilized_against_previous=stabilized,
            counterexample=counterexample,
        )
        self._stages.append(stage)
        return stage
