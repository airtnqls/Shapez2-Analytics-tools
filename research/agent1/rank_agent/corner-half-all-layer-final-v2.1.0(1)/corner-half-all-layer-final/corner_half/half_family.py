"""Exact all-layer membership theorem for buildable quad half-shapes.

A half occupies two adjacent columns.  The theorem implemented here is:

    H=(u,v) is buildable  <=>
        u and v are craftable Corner-language columns, and H is stable.

Necessity is immediate.  Sufficiency uses the Corner constructor with stable
helper towers, one Swapper recombination, rotation, and a final Cutter.  The
final cut half is unchanged because H is stable.

Runtime membership is served by the equivalent frozen 210-state minimal DFA;
semantic analysis is retained for rejection explanations and parent witnesses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .corner_dfa import RejectionCertificate, first_rejection, is_craftable_column
from .interfaces import HalfCertificate, HalfOp, HalfResult
from .half_automaton import HALF_DFA
from .structural_physics import EMPTY, code as encode_rows, is_stable


@dataclass(frozen=True)
class HalfAnalysis:
    normalized_code: str
    canonical_code: str
    cap: int
    left_column: str
    right_column: str
    left_rejection: RejectionCertificate | None
    right_rejection: RejectionCertificate | None
    stable: bool

    @property
    def buildable(self) -> bool:
        return (
            self.left_rejection is None
            and self.right_rejection is None
            and self.stable
        )


def _trim_column(chars: list[str]) -> str:
    while chars and chars[-1] == EMPTY:
        chars.pop()
    return "".join(chars)


def _parse_half(code: str, cap: int | None = None) -> tuple[list[list[str]], int]:
    if not code:
        rows: list[list[str]] = []
    else:
        rows = []
        for raw in code.split(":"):
            row = list(raw)
            if len(row) == 2:
                row += [EMPTY, EMPTY]
            if len(row) != 4:
                raise ValueError(f"half row must have 2 or 4 cells: {raw!r}")
            if any(ch not in "-SPc" for ch in row):
                raise ValueError(f"invalid half row: {raw!r}")
            if row[2] != EMPTY or row[3] != EMPTY:
                raise ValueError("half code must occupy only columns 0 and 1")
            rows.append(row)
    while rows and all(ch == EMPTY for ch in rows[-1]):
        rows.pop()
    inferred = len(rows)
    if cap is None:
        cap = inferred
    if cap < inferred:
        raise ValueError("cap is smaller than half height")
    rows += [[EMPTY] * 4 for _ in range(cap - len(rows))]
    return rows, cap


def analyze_half(code: str, layers: int | None = None) -> HalfAnalysis:
    rows, cap = _parse_half(code, layers)
    left = _trim_column([row[0] for row in rows])
    right = _trim_column([row[1] for row in rows])
    normalized = encode_rows(rows)
    swapped = [[row[1], row[0], EMPTY, EMPTY] for row in rows]
    canonical = min(normalized, encode_rows(swapped))
    left_bad = None if is_craftable_column(left) else first_rejection(left)
    right_bad = None if is_craftable_column(right) else first_rejection(right)
    stable = is_stable(rows)
    return HalfAnalysis(
        normalized,
        canonical,
        cap,
        left,
        right,
        left_bad,
        right_bad,
        stable,
    )


def is_buildable_half(code: str, layers: int | None = None) -> bool:
    """Exact Θ(L) membership through the minimized 210-state Half DFA."""
    rows, _cap = _parse_half(code, layers)
    symbols = tuple("".join(row[:2]) for row in rows)
    return HALF_DFA.accepts_rows(symbols)


class ExactHalfFamily:
    """Merge-facing exact HalfFamily implementation."""

    def contains(self, code: str, layers: int) -> bool:
        return is_buildable_half(code, layers)

    def witness(self, code: str, layers: int) -> HalfResult:
        a = analyze_half(code, layers)
        if a.buildable != is_buildable_half(code, layers):
            raise AssertionError("Half theorem and minimized DFA disagree")
        if a.left_rejection is not None:
            return HalfResult(
                False,
                a.canonical_code,
                None,
                f"left column rejected by {a.left_rejection.rule} at "
                f"{a.left_rejection.position}",
            )
        if a.right_rejection is not None:
            return HalfResult(
                False,
                a.canonical_code,
                None,
                f"right column rejected by {a.right_rejection.rule} at "
                f"{a.right_rejection.position}",
            )
        if not a.stable:
            return HalfResult(
                False,
                a.canonical_code,
                None,
                "the two craftable columns are not jointly stable",
            )
        cert = HalfCertificate(
            operation=HalfOp.CORNER_PAIR,
            parents=(a.left_column, a.right_column),
            payload=(a.cap,),
        )
        return HalfResult(
            True,
            a.canonical_code,
            cert,
            "both columns satisfy the exact Corner language and their union is stable",
        )

    def construct(self, code: str, layers: int):
        """Return the replayed stable-pair construction certificate."""
        from .half_constructor import construct_half
        return construct_half(code, layers)


HALF_FAMILY = ExactHalfFamily()


__all__ = [
    "ExactHalfFamily",
    "HALF_FAMILY",
    "HalfAnalysis",
    "analyze_half",
    "is_buildable_half",
]
