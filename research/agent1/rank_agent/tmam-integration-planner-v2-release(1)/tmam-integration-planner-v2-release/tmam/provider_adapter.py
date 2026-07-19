from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Generic, Iterable, Mapping, TypeVar

from .contracts import Coverage, Goal, InverseBatch, InverseCandidate
from .cost import CostVector
from .enums import Operation

ShapeT = TypeVar("ShapeT")


@dataclass
class CallableInverseRelationAdapter(Generic[ShapeT]):
    """Adapter for existing Claw/Hybrid/Corner provider functions.

    The callback may return an InverseBatch directly or an iterable of
    InverseCandidate objects.  This class is the intended merge boundary for
    the operation-specific branches; the planner never calls legacy classifier
    strings as an oracle.
    """

    provider_id: str
    operation: Operation
    callback: Callable[[Goal[ShapeT]], InverseBatch[ShapeT] | Iterable[InverseCandidate[ShapeT]]]
    priority: int = 100
    complete: bool = True
    coverage_reason: str = ""
    cache_token: str = "1"
    lower_bound_callback: Callable[[Goal[ShapeT]], CostVector] | None = None

    def inverse(self, goal: Goal[ShapeT]) -> InverseBatch[ShapeT]:
        result = self.callback(goal)
        if isinstance(result, InverseBatch):
            return result
        coverage = (
            Coverage.complete_result(reason=self.coverage_reason, token=self.cache_token)
            if self.complete
            else Coverage.partial(
                reason=self.coverage_reason or "legacy callback coverage is partial",
                token=self.cache_token,
            )
        )
        return InverseBatch(result, coverage, {"adapter": "callable"})

    def admissible_lower_bound(self, goal: Goal[ShapeT]) -> CostVector:
        if self.lower_bound_callback is None:
            return CostVector()
        return self.lower_bound_callback(goal)


_CORNER_FORBIDDEN = tuple(
    re.compile(pattern)
    for pattern in (
        r"-P",
        r"^P*-+c",
        r"[^P]P.*c",
        r"c-.*c",
        r"cS-+c",
        r"^S*-?S*c(.*c)?(S-+)+c",
    )
)


def legacy_corner_rule_accepts(pillar: str) -> bool:
    """The project's six proved corner forbidden rules."""

    return not any(pattern.search(pillar) for pattern in _CORNER_FORBIDDEN)
