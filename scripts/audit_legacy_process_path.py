from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "archive" / "legacy-python-gui-20260719"
sys.path.insert(0, str(LEGACY))

TARGET = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)


def main() -> None:
    from shape import Shape
    from process_tree_solver import ProcessTreeSolver

    Shape.MAX_LAYERS = 11
    solver = ProcessTreeSolver()
    root = solver.solve_process_tree(TARGET)
    data = solver.tree_to_data(root)

    # Record the reachable graph and every maximal leaf->root path.  The legacy
    # process tree stores target -> predecessor edges, so reverse each path to
    # obtain the actual forward construction order shown by the GUI.
    nodes = data.get("nodes", {})
    root_id = data.get("root_id")
    paths: list[list[dict[str, object]]] = []

    def walk(node_id: str, path: list[str], seen: set[str]) -> None:
        if node_id in seen:
            paths.append([{"cycle": node_id}])
            return
        node = nodes.get(node_id, {})
        children = list(node.get("input_ids", []))
        next_path = path + [node_id]
        if not children:
            forward = []
            for ident in reversed(next_path):
                item = nodes.get(ident, {})
                forward.append({
                    "id": ident,
                    "shape": item.get("shape_code", ""),
                    "operationToProduce": item.get("operation", ""),
                    "inputs": item.get("input_ids", []),
                })
            paths.append(forward)
            return
        for child in children:
            walk(child, next_path, seen | {node_id})

    if root_id:
        walk(root_id, [], set())

    print(json.dumps({
        "target": TARGET,
        "root": root_id,
        "nodeCount": len(nodes),
        "nodes": nodes,
        "forwardPaths": paths,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
