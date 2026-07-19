from __future__ import annotations

from dataclasses import dataclass, asdict
from time import perf_counter
from typing import Iterable, Sequence


@dataclass(frozen=True)
class WorkStats:
    layers: int
    inspections: int
    candidates: int
    materialized_cells: int
    proof_nodes: int
    proof_edges: int


@dataclass(frozen=True)
class DeltaNode:
    parent: int | None
    operation: str
    changed_rows: tuple[tuple[int, str], ...]


def make_event_word(layers: int, period: int = 5) -> tuple[str, ...]:
    if layers < period * 2 + 1:
        raise ValueError("layers too small")
    block = ("S", "-", "S", "-", "c")[:period]
    if len(block) != period:
        block = tuple(("c" if i == period - 1 else ("S" if i % 2 == 0 else "-")) for i in range(period))
    prefix = ("S",)
    repeats = (layers - 1) // period
    tail = (layers - 1) % period
    return prefix + block * repeats + block[:tail]


def naive_repeated_suffix(word: Sequence[str]) -> tuple[int, int] | None:
    """Quadratic reference: try every suffix start and block length."""
    n = len(word)
    for start in range(n):
        suffix = word[start:]
        for period in range(1, len(suffix) // 2 + 1):
            if len(suffix) % period:
                continue
            block = suffix[:period]
            if all(suffix[i] == block[i % period] for i in range(len(suffix))):
                return start, period
    return None


def event_gap_suffix(word: Sequence[str]) -> tuple[int, int, int] | None:
    """Linear event-gap recognizer used by the Half fast path.

    It assumes the event marker is c and that the event closes each candidate block.
    Returns (start, period, inspections).
    """
    events: list[int] = []
    inspections = 0
    for i, token in enumerate(word):
        inspections += 1
        if token == "c":
            events.append(i)
    if len(events) < 2:
        return None
    period = events[1] - events[0]
    if period <= 0:
        return None
    for i in range(2, len(events)):
        inspections += 1
        if events[i] - events[i - 1] != period:
            return None
    start = events[0] - period + 1
    if start < 0 or (len(word) - start) % period:
        return None
    block = word[start : start + period]
    if block[-1] != "c" or "c" in block[:-1]:
        return None
    for i in range(start, len(word)):
        inspections += 1
        if word[i] != block[(i - start) % period]:
            return None
    return start, period, inspections


def naive_stack_split(rows: Sequence[str]) -> WorkStats:
    """Generic planner model: materialize every bottom/top split."""
    n = len(rows)
    inspections = 0
    cells = 0
    candidates = 0
    for split in range(1, n):
        bottom = tuple(rows[:split])
        top = tuple(rows[split:])
        inspections += len(bottom) + len(top)
        cells += 4 * (len(bottom) + len(top))
        candidates += 1
    return WorkStats(n, inspections, candidates, cells, 1 + candidates * 3, candidates * 2)


def linear_stack_boundary(rows: Sequence[str]) -> WorkStats:
    """One-pass ownership transition scan.

    This does not claim every Stack has a unique split. It cheaply detects the
    common monotone case and returns zero candidates on ambiguity, allowing the
    generic planner to remain the exact fallback.
    """
    n = len(rows)
    owner = None
    transitions = 0
    split = None
    inspections = 0
    for i, row in enumerate(rows):
        inspections += 1
        current = "bottom" if row in {"SS", "S-", "-S"} else "top"
        if owner is None:
            owner = current
        elif current != owner:
            transitions += 1
            split = i
            owner = current
    candidates = 1 if transitions == 1 and split not in {None, 0, n} else 0
    cells = 4 * n + (2 if candidates else 0)
    nodes = 4 if candidates else 1
    edges = 3 if candidates else 0
    return WorkStats(n, inspections, candidates, cells, nodes, edges)


def eager_proof_storage(layers: int, operation_count: int) -> WorkStats:
    cells = 4 * layers * (operation_count + 1)
    return WorkStats(layers, operation_count * layers, 1, cells, operation_count + 1, operation_count)


def delta_proof_storage(layers: int, changed_rows_per_op: int, operation_count: int) -> WorkStats:
    cells = 4 * layers + changed_rows_per_op * operation_count
    return WorkStats(layers, operation_count, 1, cells, operation_count + 1, operation_count)


def lazy_materialization_cost(layers: int, operation_count: int, opened_nodes: int) -> tuple[int, int]:
    """Return eager and lazy row-cell materialization costs."""
    eager = 4 * layers * (operation_count + 1)
    opened = max(1, min(opened_nodes, operation_count + 1))
    lazy = 4 * layers + opened * layers + operation_count
    return eager, lazy


def mode_separated_work(layers: int, event_count: int) -> dict[str, int]:
    """Abstract work-unit contract for the three public modes.

    Fast verdict performs feature scan only. Analysis adds subtype facts. Proof
    additionally lowers and replays the chosen program. The constants are
    intentionally explicit so production benchmarks can replace these units
    with real timings without changing the contract.
    """
    return {
        "verdict": layers,
        "analysis": layers + event_count,
        "proof": 2 * layers + 4 * event_count,
    }


def benchmark() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for layers in (21, 41, 81, 161, 321, 641):
        word = make_event_word(layers)
        t0 = perf_counter()
        fast = event_gap_suffix(word)
        fast_us = (perf_counter() - t0) * 1_000_000
        assert fast is not None
        start, period, inspections = fast

        stack_rows = tuple("SS" if i < layers // 2 else "cS" for i in range(layers))
        naive_stack = naive_stack_split(stack_rows)
        linear_stack = linear_stack_boundary(stack_rows)

        operations = max(4, layers // 2)
        eager = eager_proof_storage(layers, operations)
        delta = delta_proof_storage(layers, 2, operations)
        eager_view, lazy_view = lazy_materialization_cost(layers, operations, opened_nodes=3)

        rows.append(
            {
                "layers": layers,
                "period": period,
                "event_gap_inspections": inspections,
                "event_gap_bound_ratio": inspections / layers,
                "event_gap_compile_us": fast_us,
                "stack_naive": asdict(naive_stack),
                "stack_linear": asdict(linear_stack),
                "stack_inspection_reduction": 1.0 - linear_stack.inspections / naive_stack.inspections,
                "stack_cell_reduction": 1.0 - linear_stack.materialized_cells / naive_stack.materialized_cells,
                "proof_eager_cells": eager.materialized_cells,
                "proof_delta_cells": delta.materialized_cells,
                "proof_cell_reduction": 1.0 - delta.materialized_cells / eager.materialized_cells,
                "view_eager_cells": eager_view,
                "view_lazy_cells": lazy_view,
                "view_cell_reduction": 1.0 - lazy_view / eager_view,
                "mode_work": mode_separated_work(layers, max(1, layers // 5)),
                "recognized_start": start,
            }
        )
    return {"schema_version": 1, "rows": rows}


if __name__ == "__main__":
    import json

    print(json.dumps(benchmark(), indent=2))
