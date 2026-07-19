from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

Row = tuple[str, str, str, str]
TARGET = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)


def parse_shape(code: str) -> tuple[Row, ...]:
    rows: list[Row] = []
    for layer in code.split(":"):
        if len(layer) != 8:
            raise ValueError(f"bad layer: {layer!r}")
        cells = tuple(layer[i : i + 2] for i in range(0, 8, 2))
        rows.append(cells)  # type: ignore[arg-type]
    return tuple(rows)


def structural_rows(rows: Sequence[Row]) -> tuple[str, ...]:
    def cell(x: str) -> str:
        if x == "--":
            return "-"
        if x[0] == "c":
            return "c"
        if x[0] == "P":
            return "P"
        return "S"

    return tuple("".join(cell(x) for x in row) for row in rows)


@dataclass(frozen=True)
class HalfProgram:
    subtype: str
    prefix: tuple[str, ...]
    block: tuple[str, ...]
    repeats: int
    events: tuple[int, ...]
    operations: tuple[str, ...]
    inspected_rows: int


@dataclass(frozen=True)
class DagStats:
    nodes: int
    edges: int
    operations: int
    materialized_row_cells: int


def compile_linear_half(code: str) -> HalfProgram | None:
    """Recognize the event-periodic two-column Half family in strict O(L).

    One scan verifies the permanent right S spine and records crystal events.
    Equal event gaps determine the only possible block length.  A second linear
    pass verifies the whole suffix.  No inverse-operation or subgoal loop is
    performed.
    """
    rows = structural_rows(parse_shape(code))
    if not rows:
        return None

    inspected = 0
    left: list[str] = []
    events: list[int] = []
    for i, row in enumerate(rows):
        inspected += 1
        if row[1] != "S" or row[2:] != "--":
            return None
        left.append(row[0])
        if row[0] == "c":
            events.append(i)

    if len(events) < 2:
        return None
    period = events[1] - events[0]
    if period <= 0 or any(events[i] - events[i - 1] != period for i in range(2, len(events))):
        return None

    # Each event is the last row of its block in the supplied legacy family.
    start = events[0] - period + 1
    if start < 0:
        return None
    suffix_len = len(left) - start
    if suffix_len < 2 * period or suffix_len % period:
        return None
    block = tuple(left[start : start + period])
    if block[-1] != "c" or "c" in block[:-1]:
        return None

    for i in range(start, len(left)):
        inspected += 1
        if left[i] != block[(i - start) % period]:
            return None
    repeats = suffix_len // period

    operations: list[str] = ["SEED"]
    for _ in range(repeats):
        # Straight sequential legacy-style macro; no reuse assumption.
        operations.extend(("PIN", "SWAP", "SWAP", "PIN"))
    return HalfProgram(
        subtype="HALF_PERIODIC_PIN_SWAP",
        prefix=tuple(left[:start]),
        block=block,
        repeats=repeats,
        events=tuple(events),
        operations=tuple(operations),
        inspected_rows=inspected,
    )


def replay_structural(program: HalfProgram) -> tuple[str, ...]:
    """Independent structural replay of the compiled witness.

    This proves exact reconstruction of the target two-column word. Integration
    into the web solver must additionally replay each primitive Pin/Swap step
    with the project physics before accepting the fast path.
    """
    left = program.prefix + program.block * program.repeats
    return tuple(ch + "S--" for ch in left)


def baseline_recursive_dag(code: str) -> DagStats:
    """Generic prefix-rematerializing proof expansion used as baseline."""
    rows = structural_rows(parse_shape(code))
    event_ends = [i + 1 for i, row in enumerate(rows) if row[0] == "c"]
    nodes = 1
    edges = 0
    operations = 0
    cells = 0
    for end in event_ends:
        nodes += end + 1
        edges += end
        operations += end
        cells += 4 * end
    nodes += len(rows) + 1
    edges += len(rows)
    operations += len(rows)
    cells += 4 * len(rows)
    return DagStats(nodes, edges, operations, cells)


def fast_linear_dag(code: str) -> DagStats | None:
    program = compile_linear_half(code)
    if program is None:
        return None
    rows = structural_rows(parse_shape(code))
    nodes = len(program.operations) + 3
    edges = len(program.operations) + 2
    operations = len(program.operations)
    cells = 4 * len(rows) + len(program.operations)
    return DagStats(nodes, edges, operations, cells)


def make_family(repeats: int) -> str:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    prefix = ("SS",)
    block = ("SS", "-S", "SS", "-S", "cS")
    words = prefix + block * repeats
    mapping = {"SS": "SuSu----", "-S": "--Su----", "cS": "cwSu----"}
    return ":".join(mapping[x] for x in words)


def benchmark(max_repeats: int = 128) -> dict[str, object]:
    result_rows = []
    for repeats in (2, 4, 8, 16, 32, 64, max_repeats):
        code = make_family(repeats)
        t0 = perf_counter()
        program = compile_linear_half(code)
        elapsed_us = (perf_counter() - t0) * 1_000_000
        fast = fast_linear_dag(code)
        base = baseline_recursive_dag(code)
        assert program is not None and fast is not None
        assert replay_structural(program) == structural_rows(parse_shape(code))
        result_rows.append(
            {
                "repeats": repeats,
                "layers": len(parse_shape(code)),
                "inspected_rows": program.inspected_rows,
                "baseline_nodes": base.nodes,
                "fast_nodes": fast.nodes,
                "node_reduction": 1.0 - fast.nodes / base.nodes,
                "baseline_cells": base.materialized_row_cells,
                "fast_cells": fast.materialized_row_cells,
                "cell_reduction": 1.0 - fast.materialized_row_cells / base.materialized_row_cells,
                "compile_us": elapsed_us,
            }
        )
    return {"target": TARGET, "rows": result_rows}


if __name__ == "__main__":
    import json

    print(json.dumps(benchmark(), indent=2))
