from __future__ import annotations

from enum import Enum, IntEnum


class Operation(str, Enum):
    """Structural operations understood by the integration layer."""

    INPUT = "input"
    ROTATE = "rotate"
    PAINT = "paint"
    CUT = "cut"
    SWAP = "swap"
    STACK = "stack"
    PIN_PUSH = "pin_push"
    GENERATOR = "generator"


class Decision(str, Enum):
    """Internal three-valued evidence using the project's UNKNOWN vocabulary."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"

    INCOMPLETE = "unknown"  # compatibility alias


class LegacyShapeTypeKey(str, Enum):
    """Stable, non-localized keys matching the legacy classifier enum names."""

    EMPTY = "EMPTY"
    SIMPLE_CORNER = "SIMPLE_CORNER"
    STACK_CORNER = "STACK_CORNER"
    SWAP_CORNER = "SWAP_CORNER"
    CLAW_CORNER = "CLAW_CORNER"
    CLAW_HYBRID_CORNER = "CLAW_HYBRID_CORNER"
    BASIC = "BASIC"
    SIMPLE = "SIMPLE"
    SWAPABLE = "SWAPABLE"  # Kept misspelled for compatibility.
    HYBRID = "HYBRID"
    COMPLEX_HYBRID = "COMPLEX_HYBRID"
    CLAW = "CLAW"
    CLAW_HYBRID = "CLAW_HYBRID"
    CLAW_COMPLEX_HYBRID = "CLAW_COMPLEX_HYBRID"
    UNKNOWN = "UNKNOWN"
    IMPOSSIBLE = "IMPOSSIBLE"


class ProofStatus(str, Enum):
    """Public possibility status.

    ``BUILDABLE`` and ``INCOMPLETE`` remain aliases for compatibility with the
    first integration prototype.  New code should use POSSIBLE / IMPOSSIBLE /
    UNKNOWN, matching the legacy GUI vocabulary requested by the project.
    """

    POSSIBLE = "possible"
    IMPOSSIBLE = "impossible"
    UNKNOWN = "unknown"

    BUILDABLE = "possible"  # compatibility alias
    INCOMPLETE = "unknown"  # compatibility alias


class SearchMode(str, Enum):
    EXISTS = "exists"
    MIN_COST = "min_cost"
    ALL_OPS = "all_ops"


class ClassificationMode(str, Enum):
    """Policy for collapsing mathematical facts to one legacy UI label."""

    LEGACY_COMPAT = "legacy_compat"
    PROOF_FIRST = "proof_first"


class CostAggregation(str, Enum):
    TREE = "tree"
    UNIQUE_SHAPES = "unique_shapes"
    CRITICAL_PATH = "critical_path"


class CoverageKind(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class Phase(IntEnum):
    """Suggested final component of a well-founded progress key."""

    INPUT = 0
    BASE_FAMILY = 10
    GENERATOR = 20
    STACK = 30
    PIN_PUSH = 40
