from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from stack_pp.rows import CRYSTAL, EMPTY, NORMAL, PIN, RowInfo
from stack_pp.stack_product import StackFamilyProductDAG


class AllFamily:
    name = "all-stable-A"

    def start_state(self):
        return 0

    def advance(self, state, row_signature):
        return state

    def accepts(self, state):
        return True


def parse(code: str) -> tuple[RowInfo, ...]:
    mapping = {"-": EMPTY, "S": NORMAL, "P": PIN, "c": CRYSTAL}
    rows = []
    for layer in code.strip().split(":"):
        if len(layer) != 4:
            raise ValueError(f"expected simplified 4-cell row: {layer!r}")
        rows.append(RowInfo.from_cells(mapping[ch] for ch in layer))
    while rows and rows[-1].occupied == 0:
        rows.pop()
    return tuple(rows)


def main() -> int:
    source = Path('/mnt/data/all40171clawsnohybrid_정렬됨_claw_complex_hybrid.txt')
    lines = [line.strip() for line in source.read_text(encoding='utf-8').splitlines() if line.strip()]
    counts = []
    nodes = []
    edges = []
    zero = []
    start = time.perf_counter()
    for index, code in enumerate(lines, 1):
        dag = StackFamilyProductDAG(parse(code), AllFamily())
        stats = dag.statistics()
        counts.append(stats.path_count)
        nodes.append(stats.reachable_nodes)
        edges.append(stats.viable_edges)
        if not stats.path_count:
            zero.append({"line": index, "shape": code})
    report = {
        "samples": len(lines),
        "zero_raw_stack_paths": len(zero),
        "zero_examples": zero[:20],
        "path_count": {
            "min": min(counts) if counts else 0,
            "max": max(counts) if counts else 0,
            "mean": statistics.mean(counts) if counts else 0,
            "median": statistics.median(counts) if counts else 0,
            "total": sum(counts),
        },
        "reachable_nodes_max": max(nodes) if nodes else 0,
        "viable_edges_max": max(edges) if edges else 0,
        "seconds": time.perf_counter() - start,
    }
    out = ROOT / 'reports' / 'provided_367_product.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not zero else 1


if __name__ == '__main__':
    raise SystemExit(main())
