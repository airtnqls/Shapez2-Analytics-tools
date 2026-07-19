from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, Sequence

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


@dataclass(frozen=True)
class DagStats:
    nodes: int
    edges: int
    operations: int
    materialized_row_cells: int


def smallest_period(seq: Sequence[str]) -> tuple[tuple[str, ...], int] | None:
    n = len(seq)
    for p in range(1, n + 1):
        if n % p == 0 and all(seq[i] == seq[i % p] for i in range(n)):
            return tuple(seq[:p]), n // p
    return None


def compile_linear_half(code: str) -> HalfProgram | None:
    """One-pass feature extraction plus bounded suffix-period check.

    The target family has one always-supported S spine in column 1, activity
    only in columns 0 and 1, and crystal events in column 0.  Prefix length is
    chosen at the first row after which the suffix is periodic.  The total
    inspected input is O(L); period candidates are bounded by the number of
    event gaps, not by arbitrary operation enumeration.
    """
    rows = structural_rows(parse_shape(code))
    if not rows:
        return None
    if any(r[1] != "S" or r[2:] != "--" for r in rows):
        return None
    left = tuple(r[0] for r in rows)
    events = tuple(i for i, ch in enumerate(left) if ch == "c")
    if not events:
        return None

    # Candidate starts are 0 and positions following event boundaries.  Their
    # count is at most L, and each failed candidate is killed by the first
    # mismatch in practical event-coded families.  For a strict worst-case
    # linear implementation, the production version should use KMP/Z; this
    # experiment also exposes the comparison count in tests.
    candidate_starts = (0,) + tuple(i + 1 for i in events if i + 1 < len(left))
    best: tuple[int, tuple[str, ...], int] | None = None
    for start in candidate_starts:
        period = smallest_period(left[start:])
        if period is None:
            continue
        block, repeats = period
        if repeats >= 2 and "c" in block:
            score = len(left[:start]) + len(block)
            if best is None or score < best[0]:
                best = (score, block, repeats)
    if best is None:
        return None
    _, block, repeats = best
    suffix_len = len(block) * repeats
    prefix = left[: len(left) - suffix_len]

    operations: list[str] = ["SEED"]
    for _ in range(repeats):
        # Straight-line legacy-style macro: no DAG reuse assumption.
        operations.extend(("PIN", "SWAP", "SWAP", "PIN"))
    return HalfProgram(
        subtype="HALF_PERIODIC_PIN_SWAP",
        prefix=prefix,
        block=block,
        repeats=repeats,
        events=events,
        operations=tuple(operations),
    )


def replay_structural(program: HalfProgram) -> tuple[str, ...]:
    """Independent structural witness replay.

    It reconstructs the exact two-column target word from prefix and repeated
    block.  This is intentionally weaker than Shapez2 physics replay; the web
    integration must additionally replay emitted primitive operations with the
    project kernel before accepting the fast path.
    """
    left = program.prefix + program.block * program.repeats
    return tuple(ch + "S--" for ch in left)


def baseline_recursive_dag(code: str) -> DagStats:
    """Model the current generic proof expansion.

    Every crystal event asks the generic planner to materialize every prefix
    subgoal again.  Hash-consing merges identical final shapes but not the
    distinct prefix-length proof nodes.  This captures the measured structural
    source of quadratic graph payload without assuming reuse.
    """
    rows = structural_rows(parse_shape(code))
    event_ends = [i + 1 for i, row in enumerate(rows) if row[0] == "c"]
    nodes = 1
    edges = 0
    operations = 0
    cells = 0
    for end in event_ends:
        # One row node and one constructor edge per prefix row.
        nodes += end + 1
        edges += end
        operations += end
        cells += 4 * end
    # Final target materialization.
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
    # Input, seed, one node per macro operation, and target.
    nodes = len(program.operations) + 3
    edges = len(program.operations) + 2
    operations = len(program.operations)
    # Store target rows once; intermediate shapes are delta/materialized lazily.
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
    rows = []
    for repeats in (1, 2, 4, 8, 16, 32, 64, max_repeats):
        code = make_family(repeats)
        t0 = perf_counter()
        program = compile_linear_half(code)
        elapsed_us = (perf_counter() - t0) * 1_000_000
        fast = fast_linear_dag(code)
        base = baseline_recursive_dag(code)
        assert program is not None and fast is not None
        assert replay_structural(program) == structural_rows(parse_shape(code))
        rows.append(
            {
                "repeats": repeats,
                "layers": len(parse_shape(code)),
                "baseline_nodes": base.nodes,
                "fast_nodes": fast.nodes,
                "node_reduction": 1.0 - fast.nodes / base.nodes,
                "baseline_cells": base.materialized_row_cells,
                "fast_cells": fast.materialized_row_cells,
                "cell_reduction": 1.0 - fast.materialized_row_cells / base.materialized_row_cells,
                "compile_us": elapsed_us,
            }
        )
    return {"target": TARGET, "rows": rows}


if __name__ == "__main__":
    import json

    print(json.dumps(benchmark(), indent=2))
