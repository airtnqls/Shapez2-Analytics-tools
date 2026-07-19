from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Mapping, TypeVar

from .enums import ClassificationMode, Decision, LegacyShapeTypeKey, Operation
from .facts import ShapeFacts

ShapeT = TypeVar("ShapeT")


class ReasonCode(str, Enum):
    EMPTY = "empty"
    BASIC = "basic_input"
    POSSIBLE = "possible"
    BUILDABLE = "possible"  # compatibility alias
    PROVED_IMPOSSIBLE = "proved_impossible"
    ANALYSIS_UNKNOWN = "analysis_unknown"
    ANALYSIS_INCOMPLETE = "analysis_unknown"  # compatibility alias
    SWAP_PREIMAGE = "swap_preimage"
    STRICT_CLAW = "strict_claw"
    STACK_PREIMAGE = "stack_preimage"
    CLAW_BASE_STACK = "claw_base_stack"
    CORNER = "single_active_column"
    CRYSTAL_FREE = "crystal_free"


@dataclass(frozen=True)
class ClassificationResult:
    primary: LegacyShapeTypeKey
    reason_codes: tuple[ReasonCode, ...]
    labels: frozenset[str]
    complete: bool
    details: Mapping[str, object]


@dataclass(frozen=True)
class ClassificationPolicy:
    """Maps exact facts to the existing UI enum without driving the solver."""

    mode: ClassificationMode = ClassificationMode.LEGACY_COMPAT

    def classify(self, facts: ShapeFacts[ShapeT]) -> ClassificationResult:
        labels = set(facts.traits)
        if facts.empty:
            return self._result(LegacyShapeTypeKey.EMPTY, (ReasonCode.EMPTY,), labels, True, facts)

        if facts.buildable is Decision.UNKNOWN:
            return self._result(
                LegacyShapeTypeKey.UNKNOWN,
                (ReasonCode.ANALYSIS_UNKNOWN,),
                labels,
                False,
                facts,
            )
        if facts.buildable is Decision.NO:
            return self._result(
                LegacyShapeTypeKey.IMPOSSIBLE,
                (ReasonCode.PROVED_IMPOSSIBLE,),
                labels,
                facts.analysis_complete,
                facts,
            )

        is_basic = Operation.INPUT in facts.possible_last_operations or "basic" in labels
        if is_basic:
            primary = LegacyShapeTypeKey.BASIC
            if facts.is_corner:
                primary = LegacyShapeTypeKey.SIMPLE_CORNER
            return self._result(primary, (ReasonCode.BASIC,), labels, facts.analysis_complete, facts)

        if facts.is_corner:
            primary, reasons = self._corner_type(facts, labels)
            return self._result(primary, reasons, labels, facts.analysis_complete, facts)

        # The old analyzer treats crystal-free shapes as SIMPLE before its
        # crystal-specific Claw/Hybrid rescue path.  Preserve that in compat mode.
        if self.mode is ClassificationMode.LEGACY_COMPAT and not facts.has_crystal:
            return self._result(
                LegacyShapeTypeKey.SIMPLE,
                (ReasonCode.CRYSTAL_FREE, ReasonCode.BUILDABLE),
                labels,
                facts.analysis_complete,
                facts,
            )

        if facts.strict_claw is Decision.YES:
            return self._result(
                LegacyShapeTypeKey.CLAW,
                (ReasonCode.STRICT_CLAW,),
                labels,
                facts.analysis_complete,
                facts,
            )

        stack_type = self._stack_type(facts, labels)
        if stack_type is not None:
            primary, reason = stack_type
            return self._result(primary, reason, labels, facts.analysis_complete, facts)

        if Operation.SWAP in facts.possible_last_operations:
            return self._result(
                LegacyShapeTypeKey.SWAPABLE,
                (ReasonCode.SWAP_PREIMAGE,),
                labels,
                facts.analysis_complete,
                facts,
            )

        return self._result(
            LegacyShapeTypeKey.SIMPLE,
            (ReasonCode.BUILDABLE,),
            labels,
            facts.analysis_complete,
            facts,
        )

    def _corner_type(
        self,
        facts: ShapeFacts[ShapeT],
        labels: set[str],
    ) -> tuple[LegacyShapeTypeKey, tuple[ReasonCode, ...]]:
        if "claw_base_stack" in labels or "claw_hybrid" in labels:
            return LegacyShapeTypeKey.CLAW_HYBRID_CORNER, (
                ReasonCode.CORNER,
                ReasonCode.CLAW_BASE_STACK,
            )
        if facts.strict_claw is Decision.YES:
            return LegacyShapeTypeKey.CLAW_CORNER, (ReasonCode.CORNER, ReasonCode.STRICT_CLAW)
        if Operation.SWAP in facts.possible_last_operations:
            return LegacyShapeTypeKey.SWAP_CORNER, (ReasonCode.CORNER, ReasonCode.SWAP_PREIMAGE)
        if Operation.STACK in facts.possible_last_operations or facts.has_crystal:
            return LegacyShapeTypeKey.STACK_CORNER, (ReasonCode.CORNER, ReasonCode.STACK_PREIMAGE)
        return LegacyShapeTypeKey.SIMPLE_CORNER, (ReasonCode.CORNER, ReasonCode.BUILDABLE)

    def _stack_type(
        self,
        facts: ShapeFacts[ShapeT],
        labels: set[str],
    ) -> tuple[LegacyShapeTypeKey, tuple[ReasonCode, ...]] | None:
        if Operation.STACK not in facts.possible_last_operations and "stack" not in labels:
            return None
        claw_base = "claw_base_stack" in labels or "claw_hybrid" in labels
        simple = (
            "canonical_stack" in labels
            or "simple_hybrid" in labels
            or facts.stack_depth == 1
        )
        if claw_base:
            return (
                LegacyShapeTypeKey.CLAW_HYBRID
                if simple
                else LegacyShapeTypeKey.CLAW_COMPLEX_HYBRID,
                (ReasonCode.STACK_PREIMAGE, ReasonCode.CLAW_BASE_STACK),
            )
        return (
            LegacyShapeTypeKey.HYBRID if simple else LegacyShapeTypeKey.COMPLEX_HYBRID,
            (ReasonCode.STACK_PREIMAGE,),
        )

    @staticmethod
    def _result(
        primary: LegacyShapeTypeKey,
        reasons: tuple[ReasonCode, ...],
        labels: set[str],
        complete: bool,
        facts: ShapeFacts[ShapeT],
    ) -> ClassificationResult:
        return ClassificationResult(
            primary=primary,
            reason_codes=reasons,
            labels=frozenset(labels),
            complete=complete,
            details={
                "shape_key": facts.shape_key,
                "possible_last_operations": sorted(op.value for op in facts.possible_last_operations),
                "strict_claw": facts.strict_claw.value,
                "pp_rank": facts.minimum_pp_rank,
                "stack_depth": facts.stack_depth,
            },
        )


def map_to_legacy_enum(result: ClassificationResult, legacy_enum) -> object:
    """Return ``ShapeType.<NAME>.value`` from the existing project enum."""

    member = getattr(legacy_enum, result.primary.name)
    return member.value
