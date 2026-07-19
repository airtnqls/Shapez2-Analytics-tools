"""Immutable structural representation for Shapez 2 quad-mode shapes.

Each cell is one of four physics classes and occupies two bits::

    0 EMPTY, 1 NORMAL, 2 PIN, 3 CRYSTAL

Four columns make one byte per layer.  Layers are laid out bottom-to-top in a
single unbounded Python integer, so there is no machine-word layer limit.
Colors and ordinary-part subtypes are deliberately omitted: they do not affect
structural physics and are restored later by provenance/color passes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Iterator, Sequence

WIDTH = 4
BITS_PER_CELL = 2
BITS_PER_LAYER = WIDTH * BITS_PER_CELL
ROW_MASK = (1 << BITS_PER_LAYER) - 1


class Cell(IntEnum):
    EMPTY = 0
    NORMAL = 1
    PIN = 2
    CRYSTAL = 3


EMPTY = int(Cell.EMPTY)
NORMAL = int(Cell.NORMAL)
PIN = int(Cell.PIN)
CRYSTAL = int(Cell.CRYSTAL)

_STRUCTURAL_TO_CELL = {
    "-": EMPTY,
    "S": NORMAL,
    "C": NORMAL,
    "R": NORMAL,
    "W": NORMAL,
    "H": NORMAL,
    "F": NORMAL,
    "G": NORMAL,
    "X": NORMAL,
    "Y": NORMAL,
    "P": PIN,
    "c": CRYSTAL,
}
_CELL_TO_STRUCTURAL = "-SPc"


def cap_mask(cap: int) -> int:
    if cap < 1:
        raise ValueError("cap must be >= 1")
    return (1 << (BITS_PER_LAYER * cap)) - 1


def cell_at(bits: int, layer: int, column: int) -> int:
    if layer < 0 or not 0 <= column < WIDTH:
        return EMPTY
    return (bits >> (BITS_PER_CELL * (WIDTH * layer + column))) & 0b11


def put_cell(bits: int, layer: int, column: int, value: int) -> int:
    if layer < 0 or not 0 <= column < WIDTH:
        raise IndexError((layer, column))
    if value not in (EMPTY, NORMAL, PIN, CRYSTAL):
        raise ValueError(f"invalid cell value: {value}")
    shift = BITS_PER_CELL * (WIDTH * layer + column)
    return (bits & ~(0b11 << shift)) | (value << shift)


def row_at(bits: int, layer: int) -> int:
    if layer < 0:
        return 0
    return (bits >> (BITS_PER_LAYER * layer)) & ROW_MASK


def put_row(bits: int, layer: int, row: int) -> int:
    if layer < 0:
        raise IndexError(layer)
    if row & ~ROW_MASK:
        raise ValueError(f"row does not fit in one layer byte: {row}")
    shift = BITS_PER_LAYER * layer
    return (bits & ~(ROW_MASK << shift)) | (row << shift)


def height_of_bits(bits: int) -> int:
    if bits == 0:
        return 0
    return (bits.bit_length() - 1) // BITS_PER_LAYER + 1


def _parse_layer(layer: str) -> tuple[int, int, int, int]:
    """Parse either a four-char structural layer or an eight-char game layer."""
    if len(layer) == WIDTH:
        chars = layer
    elif len(layer) == WIDTH * 2:
        chars = layer[0::2]
    else:
        raise ValueError(
            f"layer {layer!r} has length {len(layer)}; expected 4 or 8"
        )
    try:
        return tuple(_STRUCTURAL_TO_CELL[ch] for ch in chars)  # type: ignore[return-value]
    except KeyError as exc:
        raise ValueError(f"unsupported structural symbol {exc.args[0]!r}") from exc


def parse_bits(code: str, *, cap: int | None = None) -> tuple[int, int]:
    text = code.strip()
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.find("}", start + 1)
        if end > start:
            text = text[start + 1 : end].strip()
    if not text:
        resolved_cap = 1 if cap is None else int(cap)
        return 0, resolved_cap

    raw_layers = text.split(":")
    values = [_parse_layer(layer) for layer in raw_layers]
    required = len(values)
    resolved_cap = max(1, required) if cap is None else int(cap)
    if resolved_cap < required:
        raise ValueError(f"shape has {required} layers but cap is {resolved_cap}")

    row_bytes = [
        sum(value << (BITS_PER_CELL * column) for column, value in enumerate(row_values))
        for row_values in values
    ]
    bits = int.from_bytes(bytes(row_bytes), "little") if row_bytes else 0
    return bits, resolved_cap


@dataclass(frozen=True, slots=True)
class CompactShape:
    """Hashable structural shape with an explicit finite layer cap."""

    bits: int
    cap: int

    def __post_init__(self) -> None:
        if self.cap < 1:
            raise ValueError("cap must be >= 1")
        if self.bits < 0:
            raise ValueError("bits must be nonnegative")
        if self.bits & ~cap_mask(self.cap):
            raise ValueError("shape contains cells above its cap")

    @classmethod
    def empty(cls, cap: int) -> "CompactShape":
        return cls(0, cap)

    @classmethod
    def parse(cls, code: str, *, cap: int | None = None) -> "CompactShape":
        bits, resolved_cap = parse_bits(code, cap=cap)
        return cls(bits, resolved_cap)

    @classmethod
    def from_layer_bytes(
        cls, payload: bytes | bytearray | memoryview, *, cap: int | None = None
    ) -> "CompactShape":
        raw = bytes(payload)
        resolved_cap = max(1, len(raw)) if cap is None else int(cap)
        if len(raw) > resolved_cap:
            raise ValueError("layer payload exceeds cap")
        return cls(int.from_bytes(raw, "little") if raw else 0, resolved_cap)

    @classmethod
    def from_rows(
        cls, rows: Iterable[Sequence[int]], *, cap: int | None = None
    ) -> "CompactShape":
        materialized = [tuple(int(value) for value in row) for row in rows]
        if any(len(row) != WIDTH for row in materialized):
            raise ValueError("every row must have exactly four cells")
        resolved_cap = max(1, len(materialized)) if cap is None else int(cap)
        if len(materialized) > resolved_cap:
            raise ValueError("rows exceed cap")
        row_bytes = [
            sum(value << (BITS_PER_CELL * column) for column, value in enumerate(row))
            for row in materialized
        ]
        bits = int.from_bytes(bytes(row_bytes), "little") if row_bytes else 0
        return cls(bits, resolved_cap)

    @property
    def height(self) -> int:
        return height_of_bits(self.bits)

    @property
    def is_empty(self) -> bool:
        return self.bits == 0

    def cell(self, layer: int, column: int) -> int:
        if layer >= self.cap:
            return EMPTY
        return cell_at(self.bits, layer, column)

    def row(self, layer: int) -> int:
        if layer >= self.cap:
            return 0
        return row_at(self.bits, layer)

    def with_cell(self, layer: int, column: int, value: int) -> "CompactShape":
        if not 0 <= layer < self.cap:
            raise IndexError(layer)
        return CompactShape(put_cell(self.bits, layer, column, value), self.cap)

    def with_row(self, layer: int, row: int) -> "CompactShape":
        if not 0 <= layer < self.cap:
            raise IndexError(layer)
        return CompactShape(put_row(self.bits, layer, row), self.cap)

    def iter_rows(self, *, include_cap: bool = False) -> Iterator[tuple[int, int, int, int]]:
        stop = self.cap if include_cap else self.height
        raw = self.bits.to_bytes(stop, "little") if stop else b""
        for row in raw:
            yield tuple((row >> (BITS_PER_CELL * column)) & 3 for column in range(WIDTH))  # type: ignore[misc]

    def to_layer_bytes(self, *, include_cap: bool = False) -> bytes:
        length = self.cap if include_cap else self.height
        return self.bits.to_bytes(length, "little") if length else b""

    def to_structural(self, *, empty: str = "----") -> str:
        height = self.height
        if height == 0:
            return empty
        raw = self.bits.to_bytes(height, "little")
        layers = [
            "".join(
                _CELL_TO_STRUCTURAL[(row >> (BITS_PER_CELL * column)) & 3]
                for column in range(WIDTH)
            )
            for row in raw
        ]
        return ":".join(layers)

    def to_repository_code(
        self,
        *,
        ordinary_shape: str = "S",
        ordinary_color: str = "u",
        crystal_color: str = "w",
        empty: str = "--------",
    ) -> str:
        if self.bits == 0:
            return empty
        height = self.height
        raw = self.bits.to_bytes(height, "little")
        layers: list[str] = []
        for row in raw:
            tokens: list[str] = []
            for column in range(WIDTH):
                value = (row >> (BITS_PER_CELL * column)) & 3
                if value == EMPTY:
                    tokens.append("--")
                elif value == NORMAL:
                    tokens.append(ordinary_shape + ordinary_color)
                elif value == PIN:
                    tokens.append("P-")
                else:
                    tokens.append("c" + crystal_color)
            layers.append("".join(tokens))
        return ":".join(layers)

    def recapped(self, cap: int) -> "CompactShape":
        if cap < 1:
            raise ValueError("cap must be >= 1")
        return CompactShape(self.bits & cap_mask(cap), cap)

    def __str__(self) -> str:
        return self.to_structural()

class ShapeBuilder:
    """Ephemeral mutable builder; never use it as a solver state key."""

    __slots__ = ("cap", "_rows")

    def __init__(self, cap: int, source: CompactShape | None = None) -> None:
        if cap < 1:
            raise ValueError("cap must be >= 1")
        self.cap = int(cap)
        self._rows = bytearray(self.cap)
        if source is not None:
            payload = source.recapped(self.cap).to_layer_bytes(include_cap=True)
            self._rows[:] = payload

    @classmethod
    def from_shape(cls, shape: CompactShape) -> "ShapeBuilder":
        return cls(shape.cap, shape)

    def cell(self, layer: int, column: int) -> int:
        if not 0 <= layer < self.cap or not 0 <= column < WIDTH:
            return EMPTY
        return (self._rows[layer] >> (BITS_PER_CELL * column)) & 3

    def set_cell(self, layer: int, column: int, value: int) -> None:
        if not 0 <= layer < self.cap or not 0 <= column < WIDTH:
            raise IndexError((layer, column))
        if value not in (EMPTY, NORMAL, PIN, CRYSTAL):
            raise ValueError(value)
        shift = BITS_PER_CELL * column
        self._rows[layer] = (self._rows[layer] & ~(0b11 << shift)) | (value << shift)

    def row(self, layer: int) -> int:
        if not 0 <= layer < self.cap:
            return 0
        return self._rows[layer]

    def set_row(self, layer: int, row: int) -> None:
        if not 0 <= layer < self.cap:
            raise IndexError(layer)
        if row & ~ROW_MASK:
            raise ValueError(row)
        self._rows[layer] = row

    def freeze(self) -> CompactShape:
        return CompactShape.from_layer_bytes(self._rows, cap=self.cap)

