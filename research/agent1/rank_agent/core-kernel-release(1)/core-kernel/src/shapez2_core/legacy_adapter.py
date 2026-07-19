"""Optional compatibility bridge to Shapez2-Analytics-tools' mutable Shape API."""
from __future__ import annotations

from typing import Any

from .model import CRYSTAL, EMPTY, NORMAL, PIN, CompactShape


class LegacyAdapterError(RuntimeError):
    pass


def from_legacy_shape(shape: Any, *, cap: int | None = None) -> CompactShape:
    layers = getattr(shape, "layers", None)
    if layers is None:
        raise LegacyAdapterError("object has no .layers")
    resolved_cap = int(
        cap
        if cap is not None
        else getattr(shape, "max_layers", None)
        or max(1, len(layers))
    )
    rows: list[tuple[int, int, int, int]] = []
    for layer in layers:
        quadrants = getattr(layer, "quadrants", None)
        if quadrants is None or len(quadrants) != 4:
            raise LegacyAdapterError("legacy layer must expose four .quadrants")
        values: list[int] = []
        for piece in quadrants:
            if piece is None:
                values.append(EMPTY)
            else:
                shape_name = getattr(piece, "shape", "")
                if shape_name == "P":
                    values.append(PIN)
                elif shape_name == "c":
                    values.append(CRYSTAL)
                else:
                    values.append(NORMAL)
        rows.append(tuple(values))
    return CompactShape.from_rows(rows, cap=resolved_cap)


def to_legacy_shape(
    compact: CompactShape,
    *,
    shape_module: Any | None = None,
    ordinary_shape: str = "S",
    ordinary_color: str = "u",
    crystal_color: str = "w",
) -> Any:
    if shape_module is None:
        try:
            import shape as shape_module  # type: ignore[no-redef]
        except ImportError as exc:  # pragma: no cover - environment specific
            raise LegacyAdapterError("could not import repository shape.py") from exc

    Shape = shape_module.Shape
    Layer = shape_module.Layer
    Quadrant = shape_module.Quadrant
    layers = []
    for row in compact.iter_rows():
        quadrants = []
        for value in row:
            if value == EMPTY:
                quadrants.append(None)
            elif value == NORMAL:
                quadrants.append(Quadrant(ordinary_shape, ordinary_color))
            elif value == PIN:
                quadrants.append(Quadrant("P", "u"))
            else:
                quadrants.append(Quadrant("c", crystal_color))
        layers.append(Layer(quadrants))
    result = Shape(layers)
    result.max_layers = compact.cap
    return result


def structurally_equal_legacy(compact: CompactShape, legacy_shape: Any) -> bool:
    return compact == from_legacy_shape(legacy_shape, cap=compact.cap)
