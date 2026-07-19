"""Public API for the merge-ready Shapez 2 core-kernel branch."""
from .model import (
    BITS_PER_CELL,
    BITS_PER_LAYER,
    CRYSTAL,
    EMPTY,
    NORMAL,
    PIN,
    WIDTH,
    Cell,
    CompactShape,
    ShapeBuilder,
    cap_mask,
    cell_at,
    height_of_bits,
    parse_bits,
    put_cell,
    put_row,
    row_at,
)
from .kernel import (
    CutAxis,
    apply_gravity,
    canonical,
    canonical_with_transform,
    crystal_component_positions,
    crystal_generator,
    cut,
    dihedral_variants,
    is_stable,
    mirror,
    occupied_positions,
    paint_structural,
    pin_push,
    rotate,
    shatter_crystals,
    simple_split,
    stack,
    stack_compact_equivalent,
    support_positions,
    swap,
)
from .legacy_adapter import (
    LegacyAdapterError,
    from_legacy_shape,
    structurally_equal_legacy,
    to_legacy_shape,
)

from .protocol import (
    SEMANTICS_NAME,
    SEMANTICS_VERSION,
    ForwardCall,
    Operation,
    replay,
)

__all__ = [name for name in globals() if not name.startswith("_")]
