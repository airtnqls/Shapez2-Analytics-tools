from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

PIN = 2

class ShapeLike(Protocol):
    cap: int
    def cell(self, layer: int, column: int) -> int: ...


def bottom_pin_runs(shape: ShapeLike) -> tuple[int, int, int, int]:
    runs=[]
    for q in range(4):
        k=0
        while k < shape.cap and shape.cell(k,q) == PIN:
            k += 1
        runs.append(k)
    return tuple(runs)  # type: ignore[return-value]


def receipt_rank(shape: ShapeLike) -> int:
    return sum(bottom_pin_runs(shape))

@dataclass(frozen=True)
class RankCertificate:
    target_rank: int
    pre_push_rank: int
    recursive_base_rank: int

    @property
    def valid(self) -> bool:
        return self.recursive_base_rank < self.target_rank


def certify_rank_edge(target: ShapeLike, pre_push: ShapeLike, recursive_base: ShapeLike) -> RankCertificate:
    cert=RankCertificate(receipt_rank(target), receipt_rank(pre_push), receipt_rank(recursive_base))
    if not cert.valid:
        raise ValueError(f'non-decreasing PP edge: {cert}')
    return cert
