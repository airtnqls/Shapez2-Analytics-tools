from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from corner_half.corner_full_replay import replay_corner_full
from corner_half.corner_regions import Route, analyze_column
from corner_half.proof_dag import _rotate_to_east
from corner_half.structural_ops import generate
from corner_half.structural_physics import (
    EMPTY,
    ORDINARY,
    PIN,
    code,
    column,
    is_stable,
    parse,
)


def _raw_strategy(target: str, cap: int) -> tuple[str, tuple[str, ...]]:
    """Classify the exact branch used by shape_raw_proof without materializing it.

    This avoids the old cache-sensitive instrumentation bug: shared memoized
    Half proofs made only the first parent appear to depend on them.  The
    strategy classifier examines every operand independently.
    """

    rows = parse(code(parse(target, cap)), cap)
    normalized = code(rows)
    if not normalized:
        return "direct", ()

    chars = {cell for row in rows for cell in row if cell != EMPTY}
    if chars <= {ORDINARY} or chars <= {ORDINARY, PIN}:
        return "direct", ()

    if chars <= {ORDINARY, "c"}:
        height = max(
            (layer + 1 for layer, row in enumerate(rows) if any(cell != EMPTY for cell in row)),
            default=0,
        )
        if all(cell in (ORDINARY, "c") for row in rows[:height] for cell in row):
            seed = [
                [ORDINARY if cell == ORDINARY else EMPTY for cell in row]
                for row in rows[:height]
            ]
            if is_stable(seed) and code(generate(seed, cap)) == normalized:
                return "direct", ()

    oriented = _rotate_to_east(normalized, cap)
    if oriented is not None:
        east_code, _rotation = oriented
        east_rows = parse(east_code, cap)
        if is_stable(east_rows):
            return "half", (column(east_rows, 0), column(east_rows, 1))

    return "none", ()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report_dir = root / "reports"
    columns = [
        "" if raw == "<EMPTY>" else raw
        for raw in (report_dir / "columns_cap7.txt").read_text().splitlines()
    ]
    natural = [value for value in columns if analyze_column(value).route is Route.NATURAL]

    edges: dict[str, set[str]] = defaultdict(set)
    unclassified: list[tuple[str, str]] = []

    for value in natural:
        replay = replay_corner_full(value, 7, False)
        targets: list[str] = []
        if replay.operations:
            targets.append(replay.operations[0].before)
            targets.extend(
                step.operand
                for step in replay.operations
                if step.operation in ("C1_top_deposit", "C2_anchored_deposit")
                or step.operation.startswith("swap_")
            )
        else:
            targets.append(replay.final_full_shape)

        for target in targets:
            strategy, children = _raw_strategy(target, 7)
            if strategy == "half":
                edges[value].update(children)
            elif strategy == "none":
                unclassified.append((value, target))

    assert not unclassified, unclassified[:10]
    all_children = {child for children in edges.values() for child in children}
    assert all("-" not in child for child in all_children)
    assert all(
        child.count("-") < parent.count("-")
        for parent, children in edges.items()
        for child in children
    )

    # Solid direct-prefab children do not call the general Half theorem again,
    # so the dependency graph has depth one and cannot contain a cycle.
    full_edges = {parent: sorted(children) for parent, children in sorted(edges.items())}
    compact = json.dumps(full_edges, ensure_ascii=False, separators=(",", ":")).encode()
    summary = {
        "natural_roots": len(natural),
        "half_dependent_roots": len(edges),
        "dependency_edges": sum(len(children) for children in edges.values()),
        "unique_child_columns": len(all_children),
        "max_children_per_root": max(map(len, edges.values()), default=0),
        "cycles": 0,
        "maximum_dependency_depth": 1,
        "all_children_solid": True,
        "strict_gap_decrease": True,
        "unclassified_operands": 0,
        "edge_certificate_sha256": hashlib.sha256(compact).hexdigest(),
        "child_columns": sorted(all_children),
        "out_degree_histogram": dict(sorted(Counter(map(len, edges.values())).items())),
    }
    (report_dir / "natural_corner_dependency_edges_cap7.json").write_text(
        json.dumps(full_edges, ensure_ascii=False, indent=2) + "\n"
    )
    (report_dir / "natural_corner_dependency_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(summary)


if __name__ == "__main__":
    main()
