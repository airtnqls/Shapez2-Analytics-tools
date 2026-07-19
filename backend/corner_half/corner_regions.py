"""Semantic factorization and abstract construction witnesses for a valid column."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .corner_dfa import first_rejection, is_craftable_column, normalize_column


class Route(str, Enum):
    CRYSTAL_FREE = "crystal_free"
    NATURAL = "natural"
    EVENT = "event"


class ZoneWitnessKind(str, Enum):
    NATURAL = "natural"
    PINS_ONLY = "pins_only"
    P_RECEIPT = "p_receipt"
    PASSIVE_RECEIPT = "passive_receipt"
    PAIR_ASSEMBLY = "pair_assembly"
    TOP_PARKING = "top_parking"
    BLOCK_COMPACTION = "block_compaction"


@dataclass(frozen=True)
class ColumnRegions:
    column: str
    zone: str
    segments: tuple[str, ...]
    top: str
    crystal_positions: tuple[int, ...]


@dataclass(frozen=True)
class SegmentWitness:
    segment: str
    natural: bool
    weak_strict: bool
    event_faller_from: int | None = None
    event_faller_to: int | None = None


@dataclass(frozen=True)
class ZoneWitness:
    zone: str
    pin_count: int
    body: str
    kind: ZoneWitnessKind
    event_faller_from: int | None = None
    event_faller_to: int | None = None


@dataclass(frozen=True)
class CornerWitness:
    regions: ColumnRegions
    route: Route
    zone: ZoneWitness | None
    segments: tuple[SegmentWitness, ...]


def factor_column(column: str) -> ColumnRegions:
    w = normalize_column(column)
    crystals = tuple(i for i, ch in enumerate(w) if ch == "c")
    if not crystals:
        return ColumnRegions(w, "", (), w, ())
    zone = w[: crystals[0]]
    top = w[crystals[-1] + 1 :]
    segments = tuple(
        w[a + 1 : b] for a, b in zip(crystals, crystals[1:])
    )
    return ColumnRegions(w, zone, segments, top, crystals)


def is_i_weak(s: str) -> bool:
    return s in ("", "S") or (s.startswith("S") and s.count("S") >= 2)


def is_i_nat(s: str) -> bool:
    return s == "" or (is_i_weak(s) and ("SS" in s or s.endswith("S")))


def _split_zone(z: str) -> tuple[int, str]:
    a = 0
    while a < len(z) and z[a] == "P":
        a += 1
    return a, z[a:]


def _dead_body(v: str) -> bool:
    return bool(v) and v.startswith("-") and v.endswith("-") and "SS" not in v


def is_z_nat(z: str) -> bool:
    a, v = _split_zone(z)
    return set(v) <= {"-", "S"} and not _dead_body(v)


def is_z_evt(z: str) -> bool:
    a, v = _split_zone(z)
    if set(v) - {"-", "S"}:
        return False
    content_ok = "S" in v or (not v and a >= 1)
    receipt_ok = a >= 1 or v.count("-") >= 2
    return content_ok and receipt_ok


def choose_route(regions: ColumnRegions) -> Route:
    if not regions.crystal_positions:
        if "-P" in regions.column:
            raise ValueError("invalid crystal-free column")
        return Route.CRYSTAL_FREE
    natural = is_z_nat(regions.zone) and all(is_i_nat(x) for x in regions.segments)
    if natural:
        return Route.NATURAL
    event = is_z_evt(regions.zone) and all(is_i_weak(x) for x in regions.segments)
    if event:
        return Route.EVENT
    raise ValueError("column is outside the theorem language")


def _segment_witness(segment: str, route: Route) -> SegmentWitness:
    natural = is_i_nat(segment)
    weak_strict = is_i_weak(segment) and not natural
    if route is Route.EVENT and weak_strict:
        homes = [i for i, ch in enumerate(segment) if ch == "S"]
        # The event witness can choose the last S as sigma and park it at its
        # final home after starting above the sacrificial run.  Absolute layers
        # are assigned by the compiler; these are region-relative duties.
        return SegmentWitness(segment, False, True, len(segment) - 1, homes[-1])
    return SegmentWitness(segment, natural, weak_strict)


def _zone_witness(zone: str, route: Route) -> ZoneWitness:
    a, v = _split_zone(zone)
    if route is Route.NATURAL:
        return ZoneWitness(zone, a, v, ZoneWitnessKind.NATURAL)
    if a >= 1 and not v:
        return ZoneWitness(zone, a, v, ZoneWitnessKind.PINS_ONLY)
    if a >= 1:
        homes = [i for i, ch in enumerate(v) if ch == "S"]
        return ZoneWitness(
            zone, a, v, ZoneWitnessKind.P_RECEIPT,
            len(v) - 1 if homes else None,
            homes[-1] if homes else None,
        )

    homes = [i for i, ch in enumerate(v) if ch == "S"]
    if not homes:
        raise ValueError("event zone without S")
    if homes[0] >= 2 and not _dead_body(v):
        return ZoneWitness(zone, 0, v, ZoneWitnessKind.PASSIVE_RECEIPT)
    if len(homes) == 1 and (homes[0] == 0 or _dead_body(v)):
        return ZoneWitness(zone, 0, v, ZoneWitnessKind.TOP_PARKING, len(v) - 1, homes[0])
    if len(homes) >= 2 and homes[1] >= 3:
        return ZoneWitness(zone, 0, v, ZoneWitnessKind.PAIR_ASSEMBLY, homes[1] - 1, homes[0])
    return ZoneWitness(zone, 0, v, ZoneWitnessKind.BLOCK_COMPACTION, 2, 1)


def analyze_column(column: str) -> CornerWitness:
    # Accepted columns take the 19-state DFA fast path.  The more expensive
    # six-NFA diagnostic scan is needed only to explain an actual rejection.
    if not is_craftable_column(column):
        rejection = first_rejection(column)
        assert rejection is not None
        raise ValueError(f"forbidden {rejection.rule} at {rejection.position}")
    regions = factor_column(column)
    route = choose_route(regions)
    if route is Route.CRYSTAL_FREE:
        return CornerWitness(regions, route, None, ())
    return CornerWitness(
        regions,
        route,
        _zone_witness(regions.zone, route),
        tuple(_segment_witness(x, route) for x in regions.segments),
    )
