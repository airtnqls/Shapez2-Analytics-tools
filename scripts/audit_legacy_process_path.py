from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "archive" / "legacy-python-gui-20260719"
sys.path.insert(0, str(LEGACY))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TARGET = (
    "SuSu----:SuSu----:--Su----:SuSu----:--Su----:cwSu----:"
    "SuSu----:--Su----:SuSu----:--Su----:cwSu----"
)


def build_report() -> dict[str, object]:
    from shape import Shape
    from process_tree_solver import ProcessTreeSolver

    Shape.MAX_LAYERS = 11
    solver = ProcessTreeSolver()
    root = solver.solve_process_tree(TARGET)
    data = solver.tree_to_data(root)

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
        walk(str(root_id), [], set())

    return {
        "target": TARGET,
        "root": root_id,
        "nodeCount": len(nodes),
        "nodes": nodes,
        "forwardPaths": paths,
    }


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        report = build_report()
    except BaseException as exc:  # legacy modules may raise SystemExit
        report = {
            "target": TARGET,
            "errorType": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        os.write(1, payload.encode("utf-8"))


if __name__ == "__main__":
    main()
