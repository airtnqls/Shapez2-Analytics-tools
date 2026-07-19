"""Merge-facing interfaces owned by the corner-half branch."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence


class HalfOp(str, Enum):
    # Semantic all-layer certificate: construct each column by Corner, combine
    # the two helper-supported builds with Swap, then Cut the stable pair.
    CORNER_PAIR = "corner_pair"
    SEED = "seed"
    PIN_PUSH = "pin_push"
    STACK_LAYER = "stack_layer"
    SWAP_CUT = "swap_cut"
    SWAP_PIN_CUT = "swap_pin_cut"
    SWAP_STACK_CUT = "swap_stack_cut"


@dataclass(frozen=True)
class HalfCertificate:
    operation: HalfOp
    parents: tuple[str, ...]
    payload: tuple[int, ...] = ()


@dataclass(frozen=True)
class HalfResult:
    buildable: bool
    canonical_code: str
    certificate: HalfCertificate | None
    reason: str


class CompactPhysics(Protocol):
    """Exact structural dependency supplied by ``core-kernel`` after merge.

    Every method consumes/returns normalized structural ``-/S/P/c`` codes and
    must implement the same semantics as ``structural_ops.py``.
    """

    def normalize(self, code: str, layers: int) -> str: ...
    def stable(self, code: str, layers: int) -> bool: ...
    def rotate(self, code: str, steps_cw: int, layers: int) -> str: ...
    def cut(self, code: str, layers: int) -> tuple[str, str]: ...
    def swap(self, first: str, second: str, layers: int) -> tuple[str, str]: ...
    def stack(self, bottom: str, top: str, layers: int) -> str: ...
    def generate(self, code: str, layers: int) -> str: ...
    def pin_push(self, code: str, layers: int) -> str: ...


class HalfFamily(Protocol):
    def contains(self, code: str, layers: int) -> bool: ...
    def witness(self, code: str, layers: int) -> HalfResult: ...
