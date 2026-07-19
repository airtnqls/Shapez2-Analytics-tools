from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.service import analyze, operate  # noqa: E402


def analyze_shape(code: str, cap: int | None = None, mode: str = "type") -> dict:
    layer_count = max(1, len([part for part in code.split(":") if part]))
    return analyze(code, max(cap or layer_count, layer_count), mode)


def classify_shape(code: str) -> tuple[str, str]:
    result = analyze_shape(code, mode="type")
    mapping = {
        "EMPTY": "analyzer.shape_types.empty",
        "BASIC": "analyzer.shape_types.basic",
        "HALF": "analyzer.shape_types.simple",
        "SWAPPABLE": "analyzer.shape_types.swapable",
        "STACKABLE": "analyzer.shape_types.hybrid",
        "CLAW": "analyzer.shape_types.claw",
        "CLAW_HYBRID": "analyzer.shape_types.claw_hybrid",
        "PIN_PUSH": "analyzer.shape_types.claw",
        "IMPOSSIBLE": "analyzer.shape_types.impossible",
        "UNKNOWN": "analyzer.shape_types.unknown",
    }
    # Return the same translation keys stored in ShapeType.  PyQt translates
    # them at presentation time; this module never invokes legacy classifiers.
    classification = mapping.get(result.get("shapeType", "UNKNOWN"), "analyzer.shape_types.unknown")
    reason = f"ZIP backend C{result.get('cap', '?')} · {result.get('route', '')}: {result.get('reason', '')}"
    return classification, reason


def operate_shape(operation: str, input_a: str, input_b: str = "", cap: int | None = None, paint_color: str = "u", crystal_color: str = "u") -> dict:
    layer_count = max(1, len([part for part in input_a.split(":") if part]))
    if input_b:
        layer_count = max(layer_count, len([part for part in input_b.split(":") if part]))
    return operate(operation, input_a, input_b, max(cap or layer_count, layer_count), paint_color, crystal_color)


def trace_inputs(code: str, cap: int | None = None) -> tuple[str, list[str]]:
    result = analyze_shape(code, cap, "proof")
    graph = result.get("proof") or {}
    nodes = {str(node.get("id")): node for node in graph.get("nodes", [])}
    root_id = str(graph.get("rootId") or "")
    producer = next((
        nodes.get(str(edge.get("source"))) for edge in graph.get("edges", [])
        if str(edge.get("target")) == root_id
        and nodes.get(str(edge.get("source")), {}).get("kind") == "operation"
    ), None)
    if not producer:
        return "", []
    producer_id = str(producer.get("id"))
    inputs = [
        str(nodes[str(edge.get("source"))].get("code") or "")
        for edge in graph.get("edges", [])
        if str(edge.get("target")) == producer_id
        and nodes.get(str(edge.get("source")), {}).get("kind") == "shape"
    ]
    return str(producer.get("operation") or producer.get("label") or ""), [value for value in inputs if value]
