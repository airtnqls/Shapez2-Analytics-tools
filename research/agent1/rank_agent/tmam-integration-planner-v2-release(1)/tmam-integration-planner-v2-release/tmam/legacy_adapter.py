from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from .classification import ReasonCode, map_to_legacy_enum
from .contracts import Progress
from .runtime import TMAMRuntime

ShapeT = TypeVar("ShapeT")


_DEFAULT_REASON_KEYS = {
    ReasonCode.EMPTY: "analyzer.empty",
    ReasonCode.BASIC: "analyzer.shape_types.basic",
    ReasonCode.POSSIBLE: "analyzer.buildable",
    ReasonCode.PROVED_IMPOSSIBLE: "analyzer.shape_types.impossible",
    ReasonCode.ANALYSIS_UNKNOWN: "analyzer.shape_types.unknown",
    ReasonCode.SWAP_PREIMAGE: "analyzer.shape_types.swapable",
    ReasonCode.STRICT_CLAW: "analyzer.shape_types.claw",
    ReasonCode.STACK_PREIMAGE: "analyzer.hybrid",
    ReasonCode.CLAW_BASE_STACK: "analyzer.shape_types.claw_hybrid",
    ReasonCode.CORNER: "analyzer.corner",
    ReasonCode.CRYSTAL_FREE: "analyzer.no_crystal",
}


@dataclass
class LegacyClassifierAdapter(Generic[ShapeT]):
    runtime: TMAMRuntime[ShapeT]
    legacy_shape_type_enum: object
    translator: Callable[[str], str] = lambda value: value

    def analyze(self, shape: ShapeT, progress: Progress) -> tuple[object, str]:
        # Detailed analysis is computed once. ShapeType mapping consumes its
        # facts and never invokes a tracer/provider again.
        result = self.runtime.analyze_all_ops(shape, progress).classification
        legacy_value = map_to_legacy_enum(result, self.legacy_shape_type_enum)
        reason = " | ".join(
            self.translator(_DEFAULT_REASON_KEYS[code]) for code in result.reason_codes
        )
        return legacy_value, reason
